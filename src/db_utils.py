import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('mining_sessions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mining_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  miner_name TEXT,
                  start_time TIMESTAMP,
                  end_time TIMESTAMP,
                  time_mined INTEGER,
                  rewards TEXT,
                  mining_per_cooldown INTEGER,
                  session_id TEXT UNIQUE)''')
    conn.commit()
    conn.close()

def start_mining_session(miner_name, mining_per_cooldown, session_id):
    conn = sqlite3.connect('mining_sessions.db')
    c = conn.cursor()
    c.execute("INSERT INTO mining_sessions (miner_name, start_time, mining_per_cooldown, session_id) VALUES (?, ?, ?, ?)",
              (miner_name, datetime.now(), mining_per_cooldown, session_id))
    conn.commit()
    conn.close()

def end_mining_session(miner_name, time_mined, rewards, session_id):
    conn = sqlite3.connect('mining_sessions.db')
    c = conn.cursor()
    c.execute("UPDATE mining_sessions SET end_time = ?, time_mined = ?, rewards = ? WHERE miner_name = ? AND session_id = ? AND end_time IS NULL",
              (datetime.now(), time_mined, rewards, miner_name, session_id))
    conn.commit()
    conn.close()

def get_last_mining_session(miner_name):
    conn = sqlite3.connect('mining_sessions.db')
    c = conn.cursor()
    c.execute("SELECT start_time, end_time, mining_per_cooldown, session_id FROM mining_sessions WHERE miner_name = ? ORDER BY start_time DESC LIMIT 1", (miner_name,))
    result = c.fetchone()
    conn.close()
    return result

def get_recent_mining_sessions(miner_name, limit):
    conn = sqlite3.connect('mining_sessions.db')
    c = conn.cursor()
    c.execute("SELECT * FROM mining_sessions WHERE miner_name = ? ORDER BY start_time DESC LIMIT ?", (miner_name, limit))
    result = c.fetchall()
    conn.close()
    return result

def should_start_mining(miner_name, cooldown_time):
    last_session = get_last_mining_session(miner_name)
    if not last_session:
        return True
    
    start_time, end_time, mining_per_cooldown, _ = last_session
    start_time = datetime.fromisoformat(start_time)
    
    if end_time:
        end_time = datetime.fromisoformat(end_time)
        time_since_end = datetime.now() - end_time
        
        # Check if we've completed mining_per_cooldown sessions
        recent_sessions = get_recent_mining_sessions(miner_name, mining_per_cooldown)
        if len(recent_sessions) < mining_per_cooldown or any(session[3] is None for session in recent_sessions):
            return True
        
        return time_since_end > timedelta(seconds=cooldown_time)
    else:
        # If the last session hasn't ended, we shouldn't start a new one
        return False

def get_active_session(miner_name):
    conn = sqlite3.connect('mining_sessions.db')
    c = conn.cursor()
    c.execute("SELECT * FROM mining_sessions WHERE miner_name = ? AND end_time IS NULL ORDER BY start_time DESC LIMIT 1", (miner_name,))
    result = c.fetchone()
    conn.close()
    return result
