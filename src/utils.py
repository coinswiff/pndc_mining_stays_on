import datetime
from PIL import ImageGrab, Image, ImageEnhance
import pyautogui
import pytesseract
import json
import os
import argparse
import logging
import pywinctl as pwc
import curses
import pyperclip
import time

from config import MINING_URL, OUTPUT_DIR, logging
from config import MINER_BOX_SIZE, BROWSER_TAB_SIZE

pyautogui.PAUSE = 1.5

seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

def take_screenshot(output_dir=OUTPUT_DIR):
    # Capture the entire screen
    screenshot = ImageGrab.grab()
    screenshot.save(f"{output_dir}/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg")  # Save screenshot
    return screenshot

def get_screen_size():
    return ImageGrab.grab().size

def click_on_screen(x, y):
    logging.info(f"Clicking on ({x}, {y})")
    pyautogui.moveTo(x, y)
    pyautogui.doubleClick()

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
        if 'unclaimed' in info:
            info['unclaimed'] = info['unclaimed']
        if 'boost' in info:
            info['boost'] = float(info['boost'])
        if 'time' in info:
            info['time'] = int(info['time'])
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
    y = miner_window_offset["y"] + 377
    w = 60
    h = 22 #140
    screenshot = pyautogui.screenshot(region=(x, y, w, h))
    text = pytesseract.image_to_string(screenshot, config="--psm 7")
    try:
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

def find_miner_config(config):
    miner_config = config.copy()
    all_windows = pwc.getAllWindows()
    all_window_titles = { window.title: window for window in all_windows }
    miner_count = len(miner_config["miners"])
    print(f"Found {miner_count} miners in config")
    
    def display_miner_menu(stdscr, selected_idx):
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(0, 0, "Which miner are we updating?")
        for i in range(miner_count):
            if i == selected_idx:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(i + 2, 0, f"> Miner {i + 1}")
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(i + 2, 0, f"  Miner {i + 1}")
        if selected_idx == miner_count:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(miner_count + 2, 0, "> Add a new miner")
            stdscr.attroff(curses.color_pair(1))
        else:
            stdscr.addstr(miner_count + 2, 0, "  Add a new miner")
        stdscr.addstr(h-1, 0, "Use arrow keys to navigate, Enter to select")
        stdscr.refresh()

    def get_miner_selection(stdscr):
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        selected_idx = 0
        while True:
            display_miner_menu(stdscr, selected_idx)
            key = stdscr.getch()
            if key == curses.KEY_UP and selected_idx > 0:
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < miner_count:
                selected_idx += 1
            elif key == curses.KEY_ENTER or key in [10, 13]:
                return selected_idx

    miner_choice = curses.wrapper(get_miner_selection)
    
    if miner_choice == miner_count:
        print("Adding a new miner.")
        miner_config["miners"].append({"name": f"miner{miner_count + 1}", "miner_window_offset": {}})
        miner_index = miner_count
    else:
        miner_index = miner_choice
        print(f"Updating Miner {miner_index + 1}")
 
    _config = miner_config["miners"][miner_index]
    
    def display_window_menu(stdscr, selected_idx):
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(0, 0, "Choose your miner window:")
        for idx, title in enumerate(all_window_titles.keys()):
            if idx == selected_idx:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(idx + 2, 0, f"> {title}")
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(idx + 2, 0, f"  {title}")
        stdscr.addstr(h-1, 0, "Use arrow keys to navigate, Enter to select")
        stdscr.refresh()

    def get_window_selection(stdscr):
        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        selected_idx = 0
        while True:
            display_window_menu(stdscr, selected_idx)
            key = stdscr.getch()
            if key == curses.KEY_UP and selected_idx > 0:
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < len(all_window_titles) - 1:
                selected_idx += 1
            elif key == curses.KEY_ENTER or key in [10, 13]:
                return selected_idx

    selected_idx = curses.wrapper(get_window_selection)
    
    selected_window = list(all_window_titles.values())[selected_idx]
    print("\nSelected window details:")
    print(f"Title: {selected_window.title}")
    print(f"Box dimensions: {selected_window.box}")
    offset = (selected_window.box.width - MINER_BOX_SIZE) // 2
    _config["miner_window_offset"] = {
        "x": selected_window.box.left + offset, 
        "y": selected_window.box.top + BROWSER_TAB_SIZE
    }
    print(f"Miner config: {_config}")
    return selected_window.box, miner_index

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

    if args.function == "find_miner_config":
        logging.info("Calculating miner config")
        find_miner_config(config)
    else:
        miner_config = config["miners"][args.miner_number]
        logging.info(f"Miner config: {miner_config}")

        if args.function in function_map:
            result = function_map[args.function](miner_config)
            print(result)
        else:
            logging.error(f"Function {args.function} not found")
