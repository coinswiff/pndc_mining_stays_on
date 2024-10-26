import time
import utils
import argparse
from typing import Dict, Any
import uuid

from config import logging
import db_utils

# Constants
BUTTON_OFFSETS = {
    "mine": {"x": 200, "y": 315},
    "mine_again": {"x": 200, "y": 300},
    "logo": {"x": 65, "y": 35},
    "confirm_in_wallet": {"x": 430, "y": 590},
    "claim": {"x": 200, "y": 310},
}

COOLDOWN_WAIT_TIME = 1200  # 20 minutes in seconds
MINING_CHECK_INTERVAL = 900  # 15 minutes in seconds
GENERAL_WAIT_TIME = 6
RETRY_WAIT_TIME = 30

def get_button_offset(button_name: str, miner_window_offset: Dict[str, int]) -> Dict[str, int]:
    return {
        "x": miner_window_offset["x"] + BUTTON_OFFSETS[button_name]["x"],
        "y": miner_window_offset["y"] + BUTTON_OFFSETS[button_name]["y"]
    }

def start_miner(miner_config: Dict[str, Any]) -> str:
    logging.info(f"Starting miner {miner_config['name']}")
    mine_btn_offset = get_button_offset('mine', miner_config["miner_window_offset"])
    logging.info("Clicking Mine")
    utils.click_on_screen(**mine_btn_offset)
    time.sleep(3)
    
    confirm_btn_offset = get_button_offset('confirm_in_wallet', miner_config["miner_window_offset"])
    logging.info("Clicking Confirm in Wallet")
    utils.click_on_screen(**confirm_btn_offset)
    time.sleep(GENERAL_WAIT_TIME)  # wait for the miner to start mining
    
    mining_info = utils.get_miner_info(miner_config)
    if mining_info.get('status', 'UNKNOWN')== "MINING":
        session_id = str(uuid.uuid4())
        db_utils.start_mining_session(miner_config["name"], miner_config["mining_per_cooldown"], session_id)
        logging.info(f"Started new mining session: {session_id}")
        return session_id
    else:
        raise Exception("Miner is not mining")

def handle_claiming_status(miner_config: Dict[str, Any], skip_cooldown: bool) -> bool:
    should_mine = db_utils.should_start_mining(miner_config["name"], COOLDOWN_WAIT_TIME)
    
    if should_mine or skip_cooldown:
        logging.info("Miner is done waiting. Moving on")
        logo_btn_offset = get_button_offset('logo', miner_config["miner_window_offset"])
        logging.info("Clicking Logo")
        utils.click_on_screen(**logo_btn_offset)
        time.sleep(GENERAL_WAIT_TIME/2)
        return True
    else:
        logging.info(f"Miner is claiming. Waiting for {COOLDOWN_WAIT_TIME} seconds")
        time.sleep(COOLDOWN_WAIT_TIME)
        logo_btn_offset = get_button_offset('logo', miner_config["miner_window_offset"])
        logging.info("Clicking Logo")
        utils.click_on_screen(**logo_btn_offset)
        time.sleep(GENERAL_WAIT_TIME/2)
        return False

def handle_mining_status(miner_config: Dict[str, Any]) -> Dict[str, Any]:
    mining_info = utils.get_miner_info(miner_config)
    if 'hashrate' not in mining_info:
        # maybe we need to try again one time
        logging.info("Hashrate not found. Waiting for 10 seconds")
        time.sleep(10)
        mining_info = utils.get_miner_info(miner_config)
    
    if 'hashrate' not in mining_info:
        logging.info("Hashrate not found. Try again in a bit")
        time.sleep(10)
        return False, None
    else:
        if mining_info["hashrate"] == 0:
            logging.info("Hashrate went to zero. Claiming now")
            stop_and_claim_btn_offset = get_button_offset('claim', miner_config["miner_window_offset"])
            logging.info("Clicking Stop_And_Claim")
            utils.click_on_screen(**stop_and_claim_btn_offset)
            active_session = db_utils.get_active_session(miner_config["name"])
            if active_session:
                session_id = active_session[7]  # Assuming session_id is the 8th column
                db_utils.end_mining_session(miner_config["name"], mining_info["time"], mining_info["unclaimed"], session_id)
            
            # Check if we need to wait for cooldown
            if db_utils.should_start_mining(miner_config["name"], COOLDOWN_WAIT_TIME):
                logging.info(f"Completed mining_per_cooldown sessions. Waiting for {COOLDOWN_WAIT_TIME // 60} minutes")
                time.sleep(COOLDOWN_WAIT_TIME)
            else:
                logging.info("Can start mining immediately")
            
            return True, mining_info
        else:
            logging.info(f"Miner is mining with hashrate: {mining_info['hashrate']}. Waiting for {MINING_CHECK_INTERVAL // 60} minutes")
            time.sleep(MINING_CHECK_INTERVAL)
            return False, mining_info

def mine_pond(miner_config: Dict[str, Any], skip_cooldown: bool) -> None:
    while True:
        logging.info("Checking miner status")
        status = utils.get_miner_status(miner_config)
        
        if status == "CLAIMING":
            should_mine = handle_claiming_status(miner_config, skip_cooldown)
            if should_mine:
                logging.info("Should mine. Starting new miner")
                utils.goto_miner_page(miner_config)
                start_miner(miner_config)
        elif status == "MINING":
            claimed, mining_info = handle_mining_status(miner_config)
            if claimed:
                logging.info("Mining session ended. Starting a new one.")
                utils.goto_miner_page(miner_config)
                start_miner(miner_config)
        else:
            # We have to check if we got into a loop here. Find out where we are
            in_mining_page = utils.is_miner_page(miner_config)
            if not in_mining_page:
                logging.info("We are not in the mining page. Going back to the miner page")
                utils.goto_miner_page(miner_config)
            
            start_miner(miner_config)
    
        time.sleep(GENERAL_WAIT_TIME)

def main():
    parser = argparse.ArgumentParser(description="Manage POND mining operations")
    parser.add_argument("function", type=str, help="Function to run")
    parser.add_argument("miner_number", type=int, help="Miner number to check status for")
    parser.add_argument("--skip-cooldown", action="store_true", help="Skip waiting for the cooldown")
    args = parser.parse_args()

    config = utils.load_config_from_json()
    miner_config = config["miners"][args.miner_number]

    db_utils.init_db()  # Initialize the database

    if args.function == "start_miner":
        start_miner(miner_config)
    elif args.function == "mine_pond":
        skip_cooldown = args.skip_cooldown
        mine_pond(miner_config, skip_cooldown)

if __name__ == "__main__":
    main()
