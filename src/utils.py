import datetime
from PIL import ImageGrab, Image, ImageEnhance
import pyautogui
import pytesseract
import json
import argparse
import logging
import pyperclip
import time

from config import MINING_URL, OUTPUT_DIR, logging

pyautogui.PAUSE = 1.5

seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

def take_screenshot(output_dir=OUTPUT_DIR):
    # Capture the entire screen
    screenshot = ImageGrab.grab()
    screenshot.save(f"{output_dir}/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg")  # Save screenshot
    return screenshot

def get_screen_size():
    return ImageGrab.grab().size

def click_on_screen(x, y, double_click=True):
    logging.info(f"Clicking on ({x}, {y})")
    pyautogui.moveTo(x, y)
    if double_click:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y)

def find_button_coordinates(btn_name):
    image_path = f"assets/{btn_name}_btn.png"
    button = pyautogui.locateOnScreen(image_path)
    if button:
        x, y = pyautogui.center(button)
        return x, y
    else:
        return None

def preprocess_image(img: Image.Image):
    img = ImageEnhance.Contrast(img.convert('L')).enhance(2) # Convert to grayscale first and then enhance contrast
    img = ImageEnhance.Brightness(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(2)
    return img

def parse_time_to_seconds(time_str):
    time_parts = time_str.split(':')
    if len(time_parts) == 1:
        return int(time_parts[0])  # seconds
    elif len(time_parts) == 2:
        return int(time_parts[0]) * 60 + int(time_parts[1])  # minutes:seconds
    elif len(time_parts) == 3:
        return int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + int(time_parts[2])  # hours:minutes:seconds
    else:
        logging.warning(f"Unexpected time format: {time_str}")
        return 0

def grab_mining_info(status_img):
    preprocessed_img = preprocess_image(status_img)
    text = pytesseract.image_to_string(status_img, config="--psm 6")
    logging.debug(f"OCR Text: {text}")
    
    info = {}
    for line in text.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            info[key.strip().lower()] = value.strip()

    # Convert numeric values to appropriate types
    try:
        if 'status' in info:
            info['status'] = info['status'].replace(".", "").upper()
        if 'unclaimed' in info:
            info['unclaimed'] = info['unclaimed']
        if 'boost' in info:
            info['boost'] = float(info['boost'])
        if 'time' in info:
            info['time'] = parse_time_to_seconds(info['time'])
        else:
            info['time'] = 0
        if 'hashrate' in info:
            info['hashrate'] = float(info['hashrate'].split()[0].replace('@','0'))
    except ValueError as e:
        logging.error(f"Error converting values: {e}")

    logging.info(f"Mining info: {info}")
    return info

def get_miner_status(miner_config):
    miner_window_offset = miner_config["miner_window_offset"]
    x = miner_window_offset["x"] + 90
    y = miner_window_offset["y"] + 92
    w = 380
    h = 21 * 2
    screenshot = pyautogui.screenshot(region=(x, y, w, h))
    try:
        text = pytesseract.image_to_string(screenshot)
        logging.debug(f"OCR Text: {text}")
        for line in text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                if key.lower() == 'status':
                    return value.strip().replace(".", "").upper()
                else:
                    logging.debug(f"Skipping line: {key} with value: {value}")
            if line.lower().strip()  == "joining":
                return "joining"
            
        raise Exception("STATUS not found in OCR text")
    except Exception as e:
        screenshot_path = f"{OUTPUT_DIR}/miner_status_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
        logging.error(f"Error getting status. Screenshot saved at {screenshot_path}")
        screenshot.save(screenshot_path)
        logging.exception(f"Error: {e}")
        return None

def convert_to_seconds(s):
    if s == "":
        raise Exception("Time input is empty")
    
    logging.info(f"Converting {s} to seconds")
    return int(s[:-1]) * seconds_per_unit[s[-1]]

def get_time_waited(miner_config):
    miner_window_offset = miner_config["miner_window_offset"]
    x = miner_window_offset["x"] + 433
    y = miner_window_offset["y"] + 328
    w = 60
    h = 26 #140
    screenshot = preprocess_image(pyautogui.screenshot(region=(x, y, w, h)))
    text = pytesseract.image_to_string(screenshot, config="--psm 7")
    try:
        if text.strip() == "th" or text.strip() == "dh" or text.strip() == "tho":
            text = "1h"
        time_waited = convert_to_seconds(text.strip())    
        return time_waited
    except Exception as e:
        screenshot_path = f"{OUTPUT_DIR}/time_waited_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
        print(f"Unable to get time waited. Screenshot saved at {screenshot_path}")
        screenshot.save(screenshot_path)
        raise e

def get_miner_info(miner_config):
    miner_window_offset = miner_config["miner_window_offset"]
    x = miner_window_offset["x"] + 50
    y = miner_window_offset["y"] + 90
    w = 380
    h = 130 #140
    screenshot = pyautogui.screenshot(region=(x, y, w, h))
    info = grab_mining_info(screenshot)
    if 'hashrate' not in info:
        screenshot_path = f"{OUTPUT_DIR}/miner_status_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
        print(f"Unable to grab hashrate, logging screenshot at {screenshot_path}")
        screenshot.save(screenshot_path)
    return info

def load_config_from_json(config_path="mining_config.json"):
    with open(config_path, 'r') as file:
        _config = json.load(file)
    
    # Default to 1 mine per cooldown if not specified
    for miner in _config["miners"]:
        if "mining_per_cooldown" not in miner:
            miner["mining_per_cooldown"] = 1
    return _config

def goto_miner_page_experimental(miner_config):
    logging.info("Going to miner page")
    x = miner_config["miner_window_offset"]["x"] + 150
    y = miner_config["miner_window_offset"]["y"] + 250
    pyautogui.click(x,y);
    pyautogui.hotkey('command', 'l')
    pyautogui.typewrite(MINING_URL + "\n")
    time.sleep(3) # Allow 3 seconds to reload
    # We might need to re-establish the connection. 
    
def goto_miner_page(miner_config):
    print("Going to miner page")
    x = miner_config["miner_window_offset"]["x"] + 50
    y = miner_config["miner_window_offset"]["y"] + 50
    pyautogui.click(x,y);
    pyautogui.scroll(-10);
    x += 200
    y += 320
    pyautogui.moveTo(x,y)
    pyautogui.click()

def is_miner_page(miner_config):
    x = miner_config["miner_window_offset"]["x"] + 175
    y = miner_config["miner_window_offset"]["y"] + 255
    pyautogui.click(x, y)
    pyautogui.hotkey('command', 'l')
    pyautogui.hotkey('command', 'c')
    url = pyperclip.paste()
    if url == MINING_URL:
        return True
    else:
        logging.debug(f"URL: {url}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get miner status")
    parser.add_argument("function", type=str, help="Function to run")
    parser.add_argument("miner_number", type=int, nargs='?', help="Miner number to check status for")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config_from_json()

    function_map = {
        "get_miner_status": get_miner_status,
        "get_time_waited": get_time_waited,
        "get_miner_info": get_miner_info,
        "goto_miner_page": goto_miner_page,
        "is_miner_page": is_miner_page
    }

    miner_config = config["miners"][args.miner_number]
    logging.info(f"Miner config: {miner_config}")

    if args.function in function_map:
        result = function_map[args.function](miner_config)
        print(result)
    else:
        logging.error(f"Function {args.function} not found")
