import time
import utils
import argparse
from typing import Dict, Any, Tuple, Optional
import uuid
import re
from dataclasses import dataclass
from config import logging
from db_utils import DatabaseManager, DBConfig
import threading

@dataclass
class MiningState:
    CLAIMING = "CLAIMING"
    MINING = "MINING"
    UNKNOWN = "UNKNOWN"

@dataclass
class MiningConfig:
    BUTTON_OFFSETS = {
        "mine": {"x": 200, "y": 315},
        "mine_again": {"x": 200, "y": 300},
        "logo": {"x": 65, "y": 33},
        "confirm_in_wallet": {"x": 430, "y": 590},  # Default position
        "claim": {"x": 200, "y": 310},
    }
    COOLDOWN_WAIT_TIME: int = 1200  # 20 minutes in seconds
    MINING_CHECK_INTERVAL: int = 300  # 5 minutes in seconds
    GENERAL_WAIT_TIME: int = 6
    RETRY_WAIT_TIME: int = 30
    MIN_REWARD_THRESHOLD: float = 100.0

class MiningSession:
    def __init__(self, miner_config: Dict[str, Any], db_manager: DatabaseManager):
        self.miner_config = miner_config
        self.db = db_manager
        self.session_id: Optional[str] = None
        self.reset_cooldown_count()
        self._lock = threading.Lock()
        
    def reset_cooldown_count(self):
        self.cooldown_count: int = self.miner_config["mining_per_cooldown"]

    def get_button_offset(self, button_name: str) -> Dict[str, int]:
        """Get button offset with window position adjustment"""
        if button_name not in MiningConfig.BUTTON_OFFSETS:
            raise ValueError(f"Unknown button: {button_name}")
            
        # Use custom offset for confirm_in_wallet button
        if button_name == "confirm_in_wallet" and "confirm_button_offset" in self.miner_config:
            offset = self.miner_config["confirm_button_offset"]
        else:
            offset = MiningConfig.BUTTON_OFFSETS[button_name]
            
        return {
            "x": self.miner_config["miner_window_offset"]["x"] + offset["x"],
            "y": self.miner_config["miner_window_offset"]["y"] + offset["y"]
        }

    def activate_window(self):
        x = self.miner_config["miner_window_offset"]["x"] + 20
        y = self.miner_config["miner_window_offset"]["y"] + 20
        logging.info("Activate Window by clicking on it")
        utils.click_on_screen(x, y, double_click=False)

    def start_mining(self) -> str:
        """Start a new mining session"""
        logging.info(f"Starting miner {self.miner_config['name']}")
        
        # Click mine button
        mine_btn_offset = self.get_button_offset('mine')
        logging.info("Clicking Mine")
        utils.click_on_screen(**mine_btn_offset)
        time.sleep(3)
        
        # Confirm in wallet
        confirm_btn_offset = self.get_button_offset('confirm_in_wallet')
        logging.info("Clicking Confirm in Wallet")
        utils.click_on_screen(**confirm_btn_offset)
        time.sleep(MiningConfig.GENERAL_WAIT_TIME)
        
        # Verify mining started successfully
        mining_info = utils.get_miner_info(self.miner_config)
        if mining_info.get('status', 'UNKNOWN') == "MINING":
            self.session_id = str(uuid.uuid4())
            self.db.start_mining_session(
                self.miner_config["name"], 
                self.session_id,
                self.cooldown_count,
                boost=mining_info.get('boost', 0)
            )
            logging.info(f"Started new mining session: {self.session_id}")
            return self.session_id
        
        raise Exception("Miner is not mining")

    def handle_claiming(self, skip_cooldown: bool) -> bool:
        """Handle miner in claiming state"""
        should_mine = self.db.should_start_mining(self.miner_config["name"])
        
        # If should_mine is True, we can proceed immediately
        if should_mine or skip_cooldown:
            logging.info("Can start mining immediately")
            self.reset_cooldown_count()
        else:
            logging.info(f"Miner is claiming. Waiting for {MiningConfig.COOLDOWN_WAIT_TIME} seconds")
            time.sleep(MiningConfig.COOLDOWN_WAIT_TIME)
        
        self.activate_window()
        logo_btn_offset = self.get_button_offset('logo')
        logging.info("Clicking Logo")
        utils.click_on_screen(**logo_btn_offset)
        time.sleep(MiningConfig.GENERAL_WAIT_TIME/2)
        return True

    def process_mining_rewards(self, mining_info: Dict[str, Any]) -> None:
        """Process and record mining rewards with proper session management"""
        with self._lock:
            active_session = self.db.get_active_session(self.miner_config["name"])
            
            if not self.session_id:
                self.session_id = active_session[0] if active_session else str(uuid.uuid4())
            
            # Use the stored session_id consistently
            if not active_session:
                logging.info("No active session found. Creating new session to record rewards.")
                self.db.start_mining_session(
                    self.miner_config["name"],
                    self.session_id,
                    self.cooldown_count,
                    boost=mining_info.get('boost', 0)
                )
            
            rewards = float(re.sub(r'[^\d.]', '', mining_info["unclaimed"]))
            if rewards < MiningConfig.MIN_REWARD_THRESHOLD:
                logging.info("Rewards are less than threshold. Saving to db as zero")
                rewards = 0
                
            self.db.end_mining_session(
                self.miner_config["name"], 
                mining_info["time"], 
                rewards, 
                self.session_id
            )
            
            # Safely decrement cooldown count
            self.cooldown_count = max(0, self.cooldown_count - 1)
            self.session_id = None  # Reset session_id after completion

    def handle_mining(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Handle miner in mining state"""
        mining_info = self._get_valid_mining_info()
        if not mining_info:
            return False, None

        if mining_info["hashrate"] == 0:
            return self._handle_zero_hashrate(mining_info)
        
        logging.info(f"Miner is mining with hashrate: {mining_info['hashrate']}. "
                    f"Waiting for {MiningConfig.MINING_CHECK_INTERVAL // 60} minutes")
        time.sleep(MiningConfig.MINING_CHECK_INTERVAL)
        return False, mining_info

    def _get_valid_mining_info(self) -> Optional[Dict[str, Any]]:
        """Get valid mining info with retry"""
        mining_info = utils.get_miner_info(self.miner_config)
        if 'hashrate' not in mining_info:
            logging.info("Hashrate not found. Waiting for 10 seconds")
            time.sleep(10)
            mining_info = utils.get_miner_info(self.miner_config)
            if 'hashrate' not in mining_info:
                logging.info("Hashrate not found. Try again in a bit")
                time.sleep(10)
                return None
        return mining_info

    def _handle_zero_hashrate(self, mining_info: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Handle case when hashrate drops to zero"""
        logging.info("Hashrate went to zero. Claiming now")
        
        # Click claim button
        stop_and_claim_btn_offset = self.get_button_offset('claim')
        logging.info("Clicking Stop_And_Claim")
        utils.click_on_screen(**stop_and_claim_btn_offset)
        
        # Process rewards
        self.process_mining_rewards(mining_info)
        
        # If should_mine is True, we can proceed immediately
        if self.db.should_start_mining(self.miner_config["name"]):
            logging.info("Can start mining immediately")
            self.reset_cooldown_count()
        else:
            logging.info(f"Completed mining_per_cooldown sessions. "
                        f"Waiting for {MiningConfig.COOLDOWN_WAIT_TIME // 60} minutes")
            time.sleep(MiningConfig.COOLDOWN_WAIT_TIME)
        
        # Return to home page
        self.activate_window()
        logo_btn_offset = self.get_button_offset('logo')
        logging.info("Clicking Logo to go to home page")
        utils.click_on_screen(**logo_btn_offset, double_click=False)
        
        return True, mining_info

def mine_pond(miner_config: Dict[str, Any], skip_cooldown: bool, db_manager: DatabaseManager) -> None:
    """Main mining loop"""
    session = MiningSession(miner_config, db_manager)
    
    while True:
        logging.info("Checking miner status")
        try:
            status = utils.get_miner_status(miner_config)
            
            if status == MiningState.CLAIMING:
                if session.handle_claiming(skip_cooldown):
                    logging.info("Should mine. Starting new miner")
                    utils.goto_miner_page(miner_config)
                    session.start_mining()
                    
            elif status == MiningState.MINING:
                claimed, mining_info = session.handle_mining()
                if claimed:
                    logging.info("Mining session ended. Starting a new one.")
                    utils.goto_miner_page(miner_config)
                    session.start_mining()
                    
            else:
                if not utils.is_miner_page(miner_config):
                    logging.info("We are not in the mining page. Going back to the miner page")
                    utils.goto_miner_page(miner_config)
                
                session.start_mining()
                
        except Exception as e:
            logging.error(f"Error in mining loop: {e}")
            logging.exception("Stack trace:")
            time.sleep(MiningConfig.RETRY_WAIT_TIME)
            
        time.sleep(MiningConfig.GENERAL_WAIT_TIME)

def main():
    parser = argparse.ArgumentParser(description="Manage POND mining operations")
    parser.add_argument("function", type=str, help="Function to run")
    parser.add_argument("miner_number", type=int, help="Miner number to check status for")
    parser.add_argument("--skip-cooldown", action="store_true", help="Skip waiting for the cooldown")
    parser.add_argument("--db-path", type=str, default="mining_sessions.db", help="Path to the database file")
    args = parser.parse_args()

    config = utils.load_config_from_json()
    miner_config = config["miners"][args.miner_number]

    # Initialize database manager
    db_manager = DatabaseManager(args.db_path)
    db_manager.init_db()

    if args.function == "start_miner":
        session = MiningSession(miner_config, db_manager)
        session.start_mining()
    elif args.function == "mine_pond":
        mine_pond(miner_config, args.skip_cooldown, db_manager)

if __name__ == "__main__":
    main()
