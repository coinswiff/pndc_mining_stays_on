import sqlite3
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Tuple, Any
from dataclasses import dataclass
from contextlib import contextmanager

@dataclass
class DBConfig:
    db_path: str = 'mining_sessions.db'

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def get_db_version(self) -> int:
        """Get current database version"""
        with self.get_connection() as conn:
            try:
                cursor = conn.execute('SELECT version FROM schema_version')
                return cursor.fetchone()[0]
            except sqlite3.OperationalError:
                # If table doesn't exist, create it and return version 0
                conn.execute('CREATE TABLE schema_version (version INTEGER)')
                conn.execute('INSERT INTO schema_version VALUES (0)')
                conn.commit()
                return 0

    def set_db_version(self, version: int) -> None:
        """Update database version"""
        with self.get_connection() as conn:
            conn.execute('UPDATE schema_version SET version = ?', (version,))
            conn.commit()

    def migrate_db(self) -> None:
        """Run all pending migrations"""
        current_version = self.get_db_version()
        
        with self.get_connection() as conn:
            try:
                for version, migration in enumerate(MIGRATIONS[current_version:], start=current_version):
                    logging.info(f"Running migration {version}")
                    conn.executescript(migration)
                    self.set_db_version(version + 1)
                    logging.info(f"Migration {version} completed successfully")
            except Exception as e:
                conn.rollback()
                logging.error(f"Error during migration: {e}")
                raise

    def init_db(self) -> None:
        """Initialize database and run migrations"""
        current_version = self.get_db_version()
        if current_version <= len(MIGRATIONS):
            self.migrate_db()

    def start_mining_session(self, miner_name: str, 
                           session_id: str, cooldown_count: int,
                           boost: Optional[float] = 0) -> None:
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO mining_sessions 
                (miner_name, start_time, session_id, cooldown_count, boost) 
                VALUES (?, ?, ?, ?, ?)
                """, (miner_name, datetime.now(), session_id, cooldown_count, boost))
            conn.commit()

    def end_mining_session(self, miner_name: str, time_mined: int, rewards: Any, 
                          session_id: str) -> None:
        with self.get_connection() as conn:
            # Convert rewards to float if it's not already
            if isinstance(rewards, str):
                try:
                    rewards = float(rewards)
                except ValueError:
                    rewards = 0.0
            
            conn.execute("""
                UPDATE mining_sessions 
                SET end_time = ?, time_mined = ?, rewards = ?
                WHERE miner_name = ? AND session_id = ? AND end_time IS NULL
                """, (datetime.now(), time_mined, rewards, miner_name, session_id))
            conn.commit()

    def get_active_session(self, miner_name: str) -> Optional[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT session_id, start_time, cooldown_count FROM mining_sessions 
                WHERE miner_name = ? AND end_time IS NULL AND cooldown_count > 0
                ORDER BY start_time DESC LIMIT 1
                """, (miner_name,))
            return cursor.fetchone()

    def should_start_mining(self, miner_name: str) -> bool:
        last_session = self.get_active_session(miner_name)
        if not last_session:
            return True
        
        # last_session is a tuple with (session_id, start_time, cooldown_count)
        _, _, cooldown_count = last_session
        return cooldown_count > 1  # only start mining if cooldown count > 1
        

# Keep MIGRATIONS as a module-level constant
MIGRATIONS = [
    # Migration 0: Initial schema
    """
    CREATE TABLE IF NOT EXISTS mining_sessions
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     miner_name TEXT,
     start_time TIMESTAMP,
     end_time TIMESTAMP,
     time_mined INTEGER,
     rewards TEXT,
     mining_per_cooldown INTEGER,
     session_id TEXT UNIQUE)
    """,
    
    # Migration 1: Fixed syntax for rewards column
    """
    BEGIN TRANSACTION;
    CREATE TABLE mining_sessions_new
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     miner_name TEXT,
     start_time TIMESTAMP,
     end_time TIMESTAMP,
     time_mined INTEGER,
     rewards REAL,
     cooldown_count INTEGER,
     session_id TEXT UNIQUE,
     boost REAL);
     
    INSERT INTO mining_sessions_new 
    (id, miner_name, start_time, end_time, time_mined, rewards, session_id)
    SELECT id, miner_name, start_time, end_time, time_mined,
           CAST(CASE 
                WHEN rewards IS NULL THEN NULL
                WHEN rewards = '' THEN NULL
                ELSE rewards 
           END AS REAL),
           session_id
    FROM mining_sessions;
    
    DROP TABLE mining_sessions;
    ALTER TABLE mining_sessions_new RENAME TO mining_sessions;
    COMMIT;
    """
]
