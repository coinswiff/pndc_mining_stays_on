import subprocess
import pywinctl
import time
from typing import Optional

class MacWindow:
    """
    A window object that mimics pywinctl's window interface.
    """
    def __init__(self, title: str, app_name: str, bounds: dict, pid: Optional[int] = None):
        self._title = title
        self._app_name = app_name
        self._left = bounds.get('left', 0)
        self._top = bounds.get('top', 0)
        self._width = bounds.get('width', 0)
        self._height = bounds.get('height', 0)
        self._pid = pid
        
    @property
    def title(self) -> str:
        return self._title
        
    @property
    def appName(self) -> str:
        return self._app_name
        
    @property
    def pid(self) -> Optional[int]:
        return self._pid
        
    @property
    def left(self) -> int:
        return self._left
        
    @property
    def top(self) -> int:
        return self._top
        
    @property
    def width(self) -> int:
        return self._width
        
    @property
    def height(self) -> int:
        return self._height
        
    @property
    def right(self) -> int:
        return self._left + self._width
        
    @property
    def bottom(self) -> int:
        return self._top + self._height
    
    def getAppName(self) -> str:
        return self._app_name
    
    def getPID(self) -> Optional[int]:
        return self._pid
        
    def box(self) -> tuple:
        """Returns the window box as (left, top, width, height)"""
        return (self._left, self._top, self._width, self._height)

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} '{self.title}' of '{self.appName}'>"

class MacWindowTracker:
    """
    A more reliable way to track active windows on macOS using both pywinctl
    and AppleScript as a fallback.
    """
    
    @staticmethod
    def get_active_window_applescript() -> Optional[MacWindow]:
        """
        Get active window information using AppleScript.
        Returns a MacWindow object or None if failed.
        """
        script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                try
                    tell process frontApp
                        set frontWindow to first window
                        set windowTitle to name of frontWindow
                        set windowBounds to bounds of frontWindow
                        return {frontApp, windowTitle, item 1 of windowBounds, item 2 of windowBounds, item 3 of windowBounds, item 4 of windowBounds}
                    end tell
                on error
                    return {frontApp, "", 0, 0, 0, 0}
                end try
            end tell
        '''
        
        try:
            result = subprocess.run(['osascript', '-e', script], 
                                 capture_output=True, 
                                 text=True)
            if result.returncode == 0:
                values = result.stdout.strip().split(', ')
                if len(values) >= 6:
                    app_name = values[0].strip()
                    window_title = values[1].strip()
                    try:
                        # Convert bounds values to integers
                        left, top, right, bottom = map(int, values[2:6])
                        width = right - left
                        height = bottom - top
                        
                        bounds = {
                            'left': left,
                            'top': top,
                            'width': width,
                            'height': height
                        }
                        
                        return MacWindow(window_title, app_name, bounds)
                    except (ValueError, IndexError):
                        pass
            return None
        except Exception as e:
            print(f"AppleScript error: {e}")
            return None

    @staticmethod
    def get_active_window() -> Optional[MacWindow]:
        """
        Get active window using multiple methods for reliability.
        Returns a MacWindow object or None if failed.
        """
        # Try pywinctl first
        try:
            win = pywinctl.getActiveWindow()
            if win and win.title:
                return win
        except Exception:
            pass

        # Fallback to AppleScript
        return MacWindowTracker.get_active_window_applescript()

    @staticmethod
    def monitor_active_window(callback_fn, interval: float = 1.0) -> None:
        """
        Continuously monitor active window and call callback_fn when it changes.
        
        Args:
            callback_fn: Function that takes MacWindow object as parameter
            interval: Polling interval in seconds
        """
        last_window = None
        
        while True:
            current_window = MacWindowTracker.get_active_window()
            print(current_window)
            print(last_window)
            if current_window and (not last_window or 
                current_window.title != last_window.title or
                current_window.getPID() != last_window.getPID()):
                
                callback_fn(current_window)
                last_window = current_window
                
            time.sleep(interval)

def basic_usage():
    # Basic usage
    tracker = MacWindowTracker()
    active_window = tracker.get_active_window()
    if active_window:
        print(f"Active window: {active_window.title}")

    # Monitor window changes
    def on_window_change(window_info):
        print(f"Window changed to: {window_info.title}")

    # Start monitoring (runs indefinitely)
    tracker.monitor_active_window(on_window_change, interval=1.0)


if __name__ == "__main__":
    basic_usage()
