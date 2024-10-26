import argparse
import logging
import pywinctl as pwc
from pymacwindow import MacWindowTracker
import curses
import time
import json
from utils import load_config_from_json
import pyautogui
from pynput import mouse

from config import MINER_BOX_SIZE, BROWSER_TAB_SIZE

def on_click(x, y, button, pressed):
    # We only care about the release event of the left mouse button
    print('{0} at {1}'.format('Pressed' if pressed else 'Released', (x, y)))
    if not pressed:
        return False  # Stop the listener

def calculate_miner_config(config):
    miner_config = config.copy()
    tracker = MacWindowTracker()
    print(f"Please click on the miner window to select it")
    # Wait for mouse click
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()

    click_position = pyautogui.position()
    print("Clicked at ", click_position)
    
    time.sleep(1)
    miner_window = tracker.get_active_window()
    box = miner_window.box

    print(f"Active window: {miner_window}")
    print(f"Box dimensions: {box}")
    
    if miner_window is None or miner_window.box is None or (miner_window.box.left == 0 and miner_window.box.top == 0):
        print("Failed to get a valid window after multiple attempts.")
        print(f"Box dimensions: {miner_window.box}")
        print("Please try again.")
        print(f"Active window: {miner_window}")
        return
    
    print(f"Title: {miner_window.title}")
    print(f"Box dimensions: {box}")
    offset = (box.width - MINER_BOX_SIZE) // 2
    miner_config["window_box"] = {
        "left": box.left,
        "top": box.top,
        "width": box.width,
        "height": box.height
    }
    
    miner_config["miner_window_offset"] = {
        "x": box.left + offset, 
        "y": box.top + BROWSER_TAB_SIZE,
    }
    print(f"Active window: {miner_window}")
    
    print(f"Miner config:")
    print(json.dumps(miner_config, indent=4))
    return miner_window

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get miner status")
    parser.add_argument("miner_number", type=int, nargs='?', help="Miner number to check status for")
    args = parser.parse_args()

    config = load_config_from_json()
    miner_number = args.miner_number
    if miner_number is None:
        miner_number = 0
    miner_config = config["miners"][miner_number]
    calculate_miner_config(miner_config)
