import os
import sys
import time
import psutil
import subprocess
from datetime import datetime
from pybenutils.utils_logger.config_logger import get_logger
from pybenutils.os_operations.window_operations import get_hwnd_by_class, get_hwnds_by_class, get_window_text
if sys.platform == 'win32':
    import win32gui
    import win32com.client
    import win32con
    import win32api
    import win32process

logger = get_logger()


def open_browser_windows(browser: str, arguments=()):
    """Open selected browser by name

    :param browser: Name of the browser (chrome, chromium, firefox, iexplore, edge)
    :param arguments: Launch shell arguments
    :return: Hwnd if browser window exist else None
    """
    cmd = []
    shell = False

    # Setting the program cmd line
    if browser.lower() in ["iexplore", "ie", "iexplore"]:
        frame_class = "IEFrame"
        cmd += ["start", "iexplore.exe"]
        shell = True
    elif browser.lower() == "firefox":
        frame_class = "MozillaWindowClass"
        cmd += ["start", "firefox.exe"]
        shell = True
    elif browser.lower() == "edge":
        frame_class = "ApplicationFrameWindow"
        cmd += ["start", "microsoft-edge:"]
        shell = True
    elif browser.lower() in ['chrome', 'chromedriver']:
        frame_class = "Chrome_WidgetWin_1"
        cmd += ["start", "chrome.exe"]
        shell = True
    elif browser == "chromium":
        frame_class = "Chrome_WidgetWin_1"
        user_name = os.getenv("USERNAME")
        chrome_non_xp_path = r"C:\\Users\\" + user_name + "\\AppData\\Local\\Chromium\\Application\\chrome.exe"
        chromium_xp_path = "C:\\Documents and Settings\\" + user_name + \
                           "\\Local Settings\\Application Data\\Chromium\\Application\\chrome.exe"
        if os.path.isfile(chrome_non_xp_path):
            cmd.append(chrome_non_xp_path)
        elif os.path.isfile(chromium_xp_path):
            cmd.append(chromium_xp_path)
        else:
            raise Exception('Chromium installation folder could not be located on the machine')
    elif browser == 'msedge':
        frame_class = "Chrome_WidgetWin_1"
        cmd += ["start", "msedge.exe"]
        shell = True
    else:
        raise Exception('Browser {brw} is not yet supported'.format(brw=browser))

    # Adding the args to the cmd
    if arguments:
        if type(arguments) in [str, bytes]:
            cmd.append(arguments)
        else:
            cmd += list(arguments)

    # Launching the browser
    try:
        sub_process = subprocess.Popen(args=cmd, shell=shell)
    except WindowsError as ex:
        logger.warning(f'First attempt to launch browser failed for error: {ex}')
        time.sleep(20)
        sub_process = subprocess.Popen(args=cmd, shell=shell)

    time.sleep(5)
    logger.debug(f'Launch return code: {sub_process.returncode}')

    # Verify the browser window detected and extracting the hwnd
    hwnd = get_hwnd_by_class(frame_class)
    logger.debug(f'Checking for an open {frame_class} window for 60 seconds')
    end_time = time.time() + 60
    while hwnd is None and time.time() < end_time:
        time.sleep(1)
        hwnd = get_hwnd_by_class(frame_class)
    logger.debug('browser: {browser} hwnd: {hwnd}'.format(browser=browser, hwnd=hwnd))
    return hwnd


def set_browser_url(hwnd: int, text: str):
    """Open desired browser and ser text into url line and press enter.

    :param hwnd: hwnd of the browser.
    :param text: The text or the url that will set to browser url line.
    """
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    window_focus_by_hwnd(hwnd)
    time.sleep(5)  # Waiting for browser redirection
    shell = win32com.client.Dispatch("WScript.Shell")
    shell.SendKeys("^l", 1)
    time.sleep(1)
    shell.SendKeys("%d", 1)
    time.sleep(1)
    shell.SendKeys(text, 1)
    time.sleep(4)
    shell.SendKeys("{ENTER}", 1)
    time.sleep(4)


def get_to_home_page(hwnd: int):
    """Description: Navigate to home page in the browser

    :param hwnd: Browser's hwnd
    """
    shell = win32com.client.Dispatch("WScript.Shell")
    window_focus_by_hwnd(hwnd)
    win32api.keybd_event(0xAC, 0, 0, 0)
    shell.SendKeys("%{HOME}", 1)
    time.sleep(1)
    shell.SendKeys("%{HOME}", 1)


def close_browser(browser: str) -> bool:
    """ close browser by name

    :param browser: Browser or process name
    :return: True if all the browser window closed successfully
    """
    if 'chrom' in browser.lower():
        return close_all_browser_windows_by_class("Chrome_WidgetWin_1")
    elif 'firefox' in browser.lower():
        return close_all_browser_windows_by_class("MozillaWindowClass")
    elif browser.lower() == 'ie' or 'explore' in browser.lower():
        return close_all_browser_windows_by_class("IEFrame")
    elif 'safari' in browser.lower():
        logger.debug('The browser Safari is not installed on Win OS. Skipping.')
        return True
    else:
        logger.warn("Failed to close browser because \"{brw}\" is not yet supported".format(brw=browser))


def close_browser_by_hwnd(hwnd: int, handle_multiple_ie_tabs=True) -> bool:
    """Close browser window by hwnd

    :param hwnd: Hwnd of the browser window
    :param handle_multiple_ie_tabs: Will attempt to press the close all tabs in IE
    :return: True if the browser window closed successfully
    """
    if not hwnd:
        logger.debug('No active hwnd was given, returns True')
        return True
    try:
        thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
        shell = win32com.client.Dispatch("WScript.Shell")
        if not window_focus_by_hwnd(hwnd):
            return True
        shell.SendKeys("%", 0)
        time.sleep(1)
        window_title = get_window_text(hwnd)
        if not window_title:
            return True
        logger.debug("Closing hwnd: {hw}, with title: {title}, time: {t}".format(hw=hwnd, title=window_title,
                                                                                 t=datetime.now()))
        # win32gui.SendMessage(hwnd, 0x10, 0, 0)
        flags = win32con.SMTO_BLOCK + win32con.SMTO_NOTIMEOUTIFNOTHUNG
        win32gui.SendMessageTimeout(hwnd, 0x10, 0, 0, flags, 1000)
        time.sleep(2)
        if handle_multiple_ie_tabs:
            logger.debug('Checking for "close all tabs" popup')
            ie_close_all_tabs_window_hwnds = get_hwnds_by_class("#32770")
            for msg_hwnd in ie_close_all_tabs_window_hwnds:
                btn_hwnd = win32gui.FindWindowEx(msg_hwnd, 0, "Button", "Close all &tabs")
                if btn_hwnd > 0:
                    win32api.PostMessage(btn_hwnd, win32con.WM_LBUTTONDOWN, 0, 0)
                    time.sleep(0.3)
                    win32api.PostMessage(btn_hwnd, win32con.WM_LBUTTONUP, 0, 0)
        end_time = time.time() + 20
        while psutil.pid_exists(pid) and time.time() < end_time:
            time.sleep(2)
        if time.time() > end_time:
            logger.error('Failed to close window {title} with pid {pid}'.format(title=window_title, pid=pid))
            return False
        return True
    except Exception as ex:
        logger.error(f'Got an error when trying to close a window with error: {ex}')
        return False


def close_browser_by_class(class_name: str) -> bool:
    """ close browser by class name

    :param class_name: browser class name
    :return: True if all the browser window closed successfully
    """
    handle_multiple_ie_tabs = class_name == 'IEFrame'
    return close_browser_by_hwnd(hwnd=get_hwnd_by_class(class_name), handle_multiple_ie_tabs=handle_multiple_ie_tabs)


def close_all_browser_windows_by_class(class_name: str) -> bool:
    """ close browser by class name

    :param class_name: browser class name
    :return: True if all the browser window closed successfully
    """
    hwnd_list = get_hwnds_by_class(class_name)
    closed_all_windows = True
    handle_multiple_ie_tabs = class_name == 'IEFrame'
    for hwnd in hwnd_list:
        if not close_browser_by_hwnd(hwnd=hwnd, handle_multiple_ie_tabs=handle_multiple_ie_tabs):
            closed_all_windows = False
    return closed_all_windows


def window_set_foreground(hwnd):
    """Bring a window to the foreground and activate it.

    :param hwnd: Hwnd of window
    """
    try:
        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetActiveWindow(hwnd)
    except Exception as ex:
        logger.warning(ex)


def key_down_and_key_up(hwnd, key):
    """Send Virtual-Key to window specific

    :param hwnd: window to send key
    :param key: Hexadecimal key
    """
    rc = win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, key, 0)
    if rc == 0:
        raise AssertionError("Down click failed")
    rc = win32api.PostMessage(hwnd, win32con.WM_KEYUP, key, 0)
    if rc == 0:
        raise AssertionError("Up click failed")


def window_focus_by_hwnd(hwnd):
    """Set focus to window by hwnd

    :param hwnd: Window Hwnd
    """
    try:
        window_set_foreground(hwnd)
        key_down_and_key_up(hwnd, 0x12)
        logger.debug("window_focus_by_hwnd")
        window_set_foreground(hwnd)
    except Exception as ex:
        logger.warning(ex)
