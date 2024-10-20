import time
import utils
import argparse
from typing import Dict, Any

from config import logging

# Constants
BUTTON_OFFSETS = {
    "mine": {"x": 200, "y": 315},
    "mine_again": {"x": 200, "y": 300},
    "confirm_in_wallet": {"x": 430, "y": 590},
    "claim": {"x": 200, "y": 310},
}

CLAIMING_WAIT_TIME = 1200  # 20 minutes in seconds
MINING_CHECK_INTERVAL = 900  # 15 minutes in seconds
GENERAL_WAIT_TIME = 10
RETRY_WAIT_TIME = 30

def get_button_offset(button_name: str, miner_window_offset: Dict[str, int]) -> Dict[str, int]:
    return {
        "x": miner_window_offset["x"] + BUTTON_OFFSETS[button_name]["x"],
        "y": miner_window_offset["y"] + BUTTON_OFFSETS[button_name]["y"]
    }

def start_miner(miner_config: Dict[str, Any]) -> None:
    logging.info(f"Starting miner {miner_config['name']}")   
    utils.goto_miner_page(miner_config)
    mine_btn_offset = get_button_offset('mine', miner_config["miner_window_offset"])
    logging.info("Clicking Mine")
    utils.click_on_screen(**mine_btn_offset)
    time.sleep(5)
    
    confirm_btn_offset = get_button_offset('confirm_in_wallet', miner_config["miner_window_offset"])
    logging.info("Clicking Confirm in Wallet")
    utils.click_on_screen(**confirm_btn_offset)
    time.sleep(GENERAL_WAIT_TIME) # wait for the miner to start mining

def handle_claiming_status(miner_config: Dict[str, Any], skip_wait: bool) -> None:
    time_waited = utils.get_time_waited(miner_config)
    if skip_wait or time_waited > CLAIMING_WAIT_TIME:
        logging.info("Miner is done waiting. Moving on")
        mine_again_btn_offset = get_button_offset('mine_again', miner_config["miner_window_offset"])
        logging.info("Clicking Mine Again")
        utils.click_on_screen(**mine_again_btn_offset)
        time.sleep(GENERAL_WAIT_TIME)
        start_miner(miner_config)
    else:
        time_to_wait = CLAIMING_WAIT_TIME - time_waited
        logging.info(f"Miner is claiming. Waiting for {time_to_wait} seconds")
        time.sleep(time_to_wait)

def handle_mining_status(miner_config: Dict[str, Any]) -> None:
    mining_info = utils.get_miner_info(miner_config)
    if 'hashrate' not in mining_info:
        # maybe we need to try again one time
        logging.info("Hashrate not found. Waiting for 10 seconds")
        time.sleep(10)
        mining_info = utils.get_miner_info(miner_config)
    
    if 'hashrate' not in mining_info:
        logging.info("Hashrate not found. Try again in a bit")
        time.sleep(10)
    else:
        if mining_info["hashrate"] == 0:
            logging.info("Hashrate went to zero. Claiming now")
            stop_and_claim_btn_offset = get_button_offset('claim', miner_config["miner_window_offset"])
            logging.info("Clicking Stop_And_Claim")
            utils.click_on_screen(**stop_and_claim_btn_offset)
            logging.info(f"Miner is claimed. Waiting for {CLAIMING_WAIT_TIME // 60} minutes")
            time.sleep(CLAIMING_WAIT_TIME)
        else:
            logging.info(f"Miner is mining with hashrate: {mining_info['hashrate']}. Waiting for {MINING_CHECK_INTERVAL // 60} minutes")
            time.sleep(MINING_CHECK_INTERVAL)

def mine_pond(miner_config: Dict[str, Any], skip_wait: bool) -> None:
    mining_session = []
    while True:
        logging.info("Checking miner status")
        status = utils.get_miner_status(miner_config)
        
        if status == "CLAIMING":
            handle_claiming_status(miner_config, skip_wait)
        elif status == "MINING":
            handle_mining_status(miner_config)
        else:
            start_miner(miner_config)
        
        time.sleep(GENERAL_WAIT_TIME)

def main():
    parser = argparse.ArgumentParser(description="Manage POND mining operations")
    parser.add_argument("function", type=str, help="Function to run")
    parser.add_argument("miner_number", type=int, help="Miner number to check status for")
    parser.add_argument("--skip-wait", action="store_true", help="Skip waiting for the miner to start mining")
    args = parser.parse_args()

    config = utils.load_config_from_json()
    miner_config = config["miners"][args.miner_number]

    if args.function == "start_miner":
        start_miner(miner_config)
    elif args.function == "mine_pond":
        skip_wait = args.skip_wait
        mine_pond(miner_config, skip_wait)


if __name__ == "__main__":
    main()
