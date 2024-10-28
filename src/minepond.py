import time
import utils
import argparse
from typing import Dict, Any, Tuple, Optional
import uuid
import re
from dataclasses import dataclass
from config import logging
import db_utils

@dataclass
class MiningConfig:
    BUTTON_OFFSETS = {
        "mine": {"x": 200, "y": 315},
        "mine_again": {"x": 200, "y": 300},
        "logo": {"x": 65, "y": 33},
        "confirm_in_wallet": {"x": 430, "y": 590},
        "claim": {"x": 200, "y": 310},
    }
    COOLDOWN_WAIT_TIME: int = 1200  # 20 minutes in seconds
    MINING_CHECK_INTERVAL: int = 300  # 5 minutes in seconds
    GENERAL_WAIT_TIME: int = 6
    RETRY_WAIT_TIME: int = 30
    MIN_REWARD_THRESHOLD: float = 100.0

class MiningSession:
    def __init__(self, miner_config: Dict[str, Any]):
        self.miner_config = miner_config
        self.session_id: Optional[str] = None

    def get_button_offset(self, button_name: str) -> Dict[str, int]:
        return {
            "x": self.miner_config["miner_window_offset"]["x"] + MiningConfig.BUTTON_OFFSETS[button_name]["x"],
            "y": self.miner_config["miner_window_offset"]["y"] + MiningConfig.BUTTON_OFFSETS[button_name]["y"]
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
            db_utils.start_mining_session(
                self.miner_config["name"], 
                self.miner_config["mining_per_cooldown"], 
                self.session_id
            )
            logging.info(f"Started new mining session: {self.session_id}")
            return self.session_id
        
        raise Exception("Miner is not mining")

    def handle_claiming(self, skip_cooldown: bool) -> bool:
        """Handle miner in claiming state"""
        should_mine = db_utils.should_start_mining(self.miner_config["name"], MiningConfig.COOLDOWN_WAIT_TIME)
        
        if not (should_mine or skip_cooldown):
            logging.info(f"Miner is claiming. Waiting for {MiningConfig.COOLDOWN_WAIT_TIME} seconds")
            time.sleep(MiningConfig.COOLDOWN_WAIT_TIME)
        else:
            logging.info("Miner is done waiting. Moving on")
        
        self.activate_window()
        logo_btn_offset = self.get_button_offset('logo')
        logging.info("Clicking Logo")
        utils.click_on_screen(**logo_btn_offset)
        time.sleep(MiningConfig.GENERAL_WAIT_TIME/2)
        return True

    def process_mining_rewards(self, mining_info: Dict[str, Any]) -> None:
        """Process and record mining rewards"""
        active_session = db_utils.get_active_session(self.miner_config["name"])
        if active_session:
            session_id = active_session[7]
            #rewards = float(re.sub(r'[mM\s]', '', mining_info["unclaimed"]))
            rewards = float(re.sub(r'[^\d.]', '', mining_info["unclaimed"]))

            if rewards < MiningConfig.MIN_REWARD_THRESHOLD:
                logging.info("Rewards are less than threshold. Saving to db as zero")
                rewards = 0
            db_utils.end_mining_session(
                self.miner_config["name"], 
                mining_info["time"], 
                rewards, 
                session_id
            )

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
        
        # Handle cooldown
        if db_utils.should_start_mining(self.miner_config["name"], MiningConfig.COOLDOWN_WAIT_TIME):
            logging.info(f"Completed mining_per_cooldown sessions. "
                        f"Waiting for {MiningConfig.COOLDOWN_WAIT_TIME // 60} minutes")
            time.sleep(MiningConfig.COOLDOWN_WAIT_TIME)
        else:
            logging.info("Can start mining immediately")
        
        # Return to home page
        self.activate_window()
        logo_btn_offset = self.get_button_offset('logo')
        logging.info("Clicking Logo to go to home page")
        utils.click_on_screen(**logo_btn_offset, double_click=False)
        
        return True, mining_info

def mine_pond(miner_config: Dict[str, Any], skip_cooldown: bool) -> None:
    """Main mining loop"""
    session = MiningSession(miner_config)
    
    while True:
        logging.info("Checking miner status")
        status = utils.get_miner_status(miner_config)
        
        try:
            if status == "CLAIMING":
                if session.handle_claiming(skip_cooldown):
                    logging.info("Should mine. Starting new miner")
                    utils.goto_miner_page(miner_config)
                    session.start_mining()
                    
            elif status == "MINING":
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
            time.sleep(MiningConfig.RETRY_WAIT_TIME)
            
        time.sleep(MiningConfig.GENERAL_WAIT_TIME)

def main():
    parser = argparse.ArgumentParser(description="Manage POND mining operations")
    parser.add_argument("function", type=str, help="Function to run")
    parser.add_argument("miner_number", type=int, help="Miner number to check status for")
    parser.add_argument("--skip-cooldown", action="store_true", help="Skip waiting for the cooldown")
    args = parser.parse_args()

    config = utils.load_config_from_json()
    miner_config = config["miners"][args.miner_number]

    db_utils.init_db()

    if args.function == "start_miner":
        session = MiningSession(miner_config)
        session.start_mining()
    elif args.function == "mine_pond":
        mine_pond(miner_config, args.skip_cooldown)

if __name__ == "__main__":
    main()
