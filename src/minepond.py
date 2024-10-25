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

COOLDOWN_WAIT_TIME = 1200  # 20 minutes in seconds
MINING_CHECK_INTERVAL = 900  # 15 minutes in seconds
GENERAL_WAIT_TIME = 6
RETRY_WAIT_TIME = 30

def get_button_offset(button_name: str, miner_window_offset: Dict[str, int]) -> Dict[str, int]:
    return {
        "x": miner_window_offset["x"] + BUTTON_OFFSETS[button_name]["x"],
        "y": miner_window_offset["y"] + BUTTON_OFFSETS[button_name]["y"]
    }

def start_miner(miner_config: Dict[str, Any]) -> None:
    logging.info(f"Starting miner {miner_config['name']}")   
    #utils.goto_miner_page(miner_config)
    mine_btn_offset = get_button_offset('mine', miner_config["miner_window_offset"])
    logging.info("Clicking Mine")
    utils.click_on_screen(**mine_btn_offset)
    time.sleep(3)
    
    confirm_btn_offset = get_button_offset('confirm_in_wallet', miner_config["miner_window_offset"])
    logging.info("Clicking Confirm in Wallet")
    utils.click_on_screen(**confirm_btn_offset)
    time.sleep(GENERAL_WAIT_TIME) # wait for the miner to start mining
    mining_session = dict(
        miner_name=miner_config["name"],
        start_time=time.time(),
        status="MINING",
        claimed=False,
        rewards=0
    )
    return mining_session

def handle_claiming_status(miner_config: Dict[str, Any], mining_count: int, skip_cooldown: bool) -> None:
    mining_per_cooldown = miner_config["mining_per_cooldown"]
    should_wait_for_cooldown = mining_count % mining_per_cooldown == 0
    skip_wait = skip_cooldown or (not should_wait_for_cooldown)
    time_waited = utils.get_time_waited(miner_config)
    if skip_wait or time_waited > COOLDOWN_WAIT_TIME:
        logging.info("Miner is done waiting. Moving on")
        mine_again_btn_offset = get_button_offset('mine_again', miner_config["miner_window_offset"])
        logging.info("Clicking Mine Again")
        utils.click_on_screen(**mine_again_btn_offset)
        time.sleep(GENERAL_WAIT_TIME/2)
        return True
    else:
        time_to_wait = COOLDOWN_WAIT_TIME - time_waited
        logging.info(f"Miner is claiming. Waiting for {time_to_wait} seconds")
        time.sleep(time_to_wait)
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
            logging.info(f"Miner is claimed. Waiting for {COOLDOWN_WAIT_TIME // 60} minutes")
            time.sleep(COOLDOWN_WAIT_TIME)
            return True, mining_info
        else:
            logging.info(f"Miner is mining with hashrate: {mining_info['hashrate']}. Waiting for {MINING_CHECK_INTERVAL // 60} minutes")
            time.sleep(MINING_CHECK_INTERVAL)
            return False, mining_info

def mine_pond(miner_config: Dict[str, Any], skip_cooldown: bool) -> None:
    mining_sessions = []
    while True:
        logging.info("Checking miner status")
        status = utils.get_miner_status(miner_config)
        
        if status == "CLAIMING":
            should_mine = handle_claiming_status(miner_config, len(mining_sessions), skip_cooldown)
            if should_mine:
                mine_session = start_miner(miner_config)
                logging.info(f"Started new mining session: {mine_session}")
                mining_sessions.append(mine_session)
        elif status == "MINING":
            claimed, mining_info = handle_mining_status(miner_config)
            if mining_info:
                if len(mining_sessions) > 0:
                    mining_sessions[-1]['rewards'] = mining_info['unclaimed']
                    mining_sessions[-1]['time'] = mining_info['time']
                    mining_sessions[-1]['claimed'] = claimed
                    logging.info(f"Updated last mining session: {mining_sessions[-1]}")
                else:
                    mining_sessions.append(dict(
                        miner_name=miner_config["name"],
                        start_time=time.time(), # Maybe get this from the time field.
                        status="MINING",
                        time=mining_info['time'],
                        claimed=claimed,
                        rewards=mining_info['unclaimed']
                    ))
                    logging.info(f"Started new mining session: {mining_sessions[-1]}")
        else:
            # We have to check if we got into a loop here. Find out where we are
            in_mining_page = utils.is_miner_page(miner_config)
            if not in_mining_page:
                logging.info("We are not in the mining page. Going back to the miner page")
                utils.goto_miner_page(miner_config)
                
            
            mine_session = start_miner(miner_config)
            logging.info(f"Started new mining session: {mine_session}")
            mining_sessions.append(mine_session)
    
        time.sleep(GENERAL_WAIT_TIME)

def main():
    parser = argparse.ArgumentParser(description="Manage POND mining operations")
    parser.add_argument("function", type=str, help="Function to run")
    parser.add_argument("miner_number", type=int, help="Miner number to check status for")
    parser.add_argument("--skip-cooldown", action="store_true", help="Skip waiting for the cooldown")
    args = parser.parse_args()

    config = utils.load_config_from_json()
    miner_config = config["miners"][args.miner_number]

    if args.function == "start_miner":
        start_miner(miner_config)
    elif args.function == "mine_pond":
        skip_cooldown = args.skip_cooldown
        mine_pond(miner_config, skip_cooldown)


if __name__ == "__main__":
    main()
