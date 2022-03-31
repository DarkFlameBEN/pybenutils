import sys
import time
from typing import List
from getpass import getuser
from psutil import NoSuchProcess
from pybenutils.utils_logger.config_logger import get_logger
from pybenutils.os_operations.process import ProcessHandler
from pybenutils.os_operations.window_operations import get_hwnds_by_class, click_on_point
from pybenutils.browsers.windows_browsers_keywords import set_browser_url, close_browser, get_to_home_page, \
    open_browser_windows
if sys.platform == 'win32':
    import win32com.client
    import win32gui
else:
    from pybenutils.os_operations.mac_operations import run_apple_script

logger = get_logger()


def kill_all_browsers(browsers_list=('iexplore.exe', 'IEDriverServer.exe', 'chrome', 'firefox', 'chromedriver',
                                     'safari', 'chromium', 'geckodriver', 'msedge'),
                      attempt_graceful_shutdown=True):
    """Closes and kills all the process sharing the given process names in the input list

    :param browsers_list: Browsers process name to kill
    :param attempt_graceful_shutdown: Attempts to close the browser before killing its processes
    """
    if type(browsers_list) == str:
        browsers_list = [browsers_list]
    for browser in browsers_list:
        brw = SimpleBrowserController(browser)
        brw.kill(attempt_graceful_shutdown=attempt_graceful_shutdown)
        time.sleep(5)


def close_all_browsers(browsers_list=('iexplore.exe', 'IEDriverServer.exe', 'chrome', 'firefox', 'chromedriver',
                                      'safari', 'chromium', 'geckodriver', 'msedge')):
    """Closes all the process sharing the given process names in the input list

    :param browsers_list: Browsers process name to kill
    """
    if type(browsers_list) == str:
        browsers_list = [browsers_list]
    for browser in browsers_list:
        brw = SimpleBrowserController(browser)
        brw.close()
        time.sleep(5)


class SimpleBrowserController:
    def __init__(self, browser_name):
        """Initiates the class

        :param browser_name: In Windows, process name. In mac: Full application path OR one of the pre-supported apps.
         Supported apps: safari, chrome, chromium, firefox, msedge
        """
        process_names_mac_conversion_table = {
            'safari': '/Applications/Safari.app',
            'chrome': '/Applications/Google Chrome.app',
            'chromium': '/Users/{u_name}/Applications/Chromium.app'.format(u_name=getuser()),
            'firefox': '/Applications/Firefox.app',
            'msedge': '/Applications/Microsoft Edge.app'
        }
        class_name_windows_conversion_table = {
            'chromedriver.exe': 'Chrome_WidgetWin_1',
            'chrome.exe': 'Chrome_WidgetWin_1',
            'firefox.exe': 'MozillaWindowClass',
            'geckodriver.exe': 'MozillaWindowClass',
            'iexplore.exe': 'IEFrame',
            'IEDriverServer.exe': 'IEFrame',
            'msedge.exe': 'Chrome_WidgetWin_1'
        }
        self.browser_name = browser_name
        if sys.platform != 'win32' and browser_name in process_names_mac_conversion_table:
            self.browser_name = process_names_mac_conversion_table[browser_name]

        self.browser_process_name = self.browser_name
        if self.browser_name in ['chrome', 'chrome.exe', 'chromium', 'chromium.exe']:
            self.browser_process_name = 'chrome.exe'
        elif sys.platform == 'win32' and not self.browser_process_name.endswith('.exe'):
            self.browser_process_name = '{brw}.exe'.format(brw=self.browser_process_name)

        self.hwnd = []
        self.app_obj = None
        if sys.platform != 'win32':
            from pybenutils.os_operations.mac_application_control import ApplicationControl
            self.app_obj = ApplicationControl(self.browser_name)
        else:
            self.class_name = class_name_windows_conversion_table[self.browser_process_name] if \
                self.browser_process_name in class_name_windows_conversion_table else ''

    def launch(self, arguments=()) -> bool:
        """Launching the app
        :param arguments: launch shell arguments
        """
        logger.info('Launching browser: {brw}{arg}'.format(
            brw=self.browser_name, arg=f' With args: {arguments}' if arguments else ''))
        if sys.platform == 'win32':
            new_handler = open_browser_windows(browser=self.browser_name, arguments=arguments)
            if not new_handler:
                return False
            self.hwnd.append(new_handler)
            return True
        else:
            return self.app_obj.launch(arguments=arguments)

    def kill(self, attempt_graceful_shutdown=True):
        """Killing the browser processes
        :param attempt_graceful_shutdown: Try to gracefully close the browser before killing it
        """
        if attempt_graceful_shutdown:
            self.close()
            time.sleep(20)
        logger.info('Killing {brw} browser instances'.format(brw=self.browser_process_name))
        if sys.platform == 'win32':
            p_handler = ProcessHandler(self.browser_process_name)
            try:
                p_handler.kill_process()
            except NoSuchProcess as ex:
                logger.warning(ex)
                time.sleep(20)
                self.kill(attempt_graceful_shutdown=attempt_graceful_shutdown)
            self.hwnd = []
        else:
            self.app_obj.kill()
        time.sleep(10)
        if ProcessHandler(self.browser_process_name).proc_list:
            logger.warning('Some processes of {na} stayed alive'.format(na=self.browser_process_name))

    def close(self) -> bool:
        """Try to gracefully close the browser
        :return: True if successful
        """
        logger.info('Trying to close the {brw} browser instances'.format(brw=self.browser_name))
        if sys.platform == 'win32':
            if close_browser(self.browser_name):
                self.hwnd = []
                return True
            self.press_enter_button()
            time.sleep(3)
            if close_browser(self.browser_name):
                self.hwnd = []
                return True
            logger.warning('{n} could not be gracefully closed'.format(n=self.browser_name))
            return False
        else:
            self.app_obj.close()
            time.sleep(3)
            return True

    def refresh_hwnd_list(self) -> List:
        self.hwnd = get_hwnds_by_class(self.class_name)
        return self.hwnd

    def get_hwnd(self) -> List:
        """Returns the hwnd list parameter"""
        return self.hwnd

    def press_key_combination_on_mac_browser(self, key_command) -> bool:
        """Attempts to press the requested command on the keyboard

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                logger.warning('You are trying to use a mac function on a windows os')
                return False
            else:
                cmd = 'tell application "{app_name}" to activate\ntell application "System Events" to' \
                      ' {key_combination}'.format(app_name=self.browser_name, key_combination=key_command)
                result = run_apple_script(cmd)
                if not result:
                    raise Exception('The Apple script has failed')
        except Exception as ex:
            logger.error('Failed to press requested keys for error: {err}'.format(err=str(ex)))
            return False
        return True

    def get_to_home_page(self) -> bool:
        """Attempts to navigate to the home page using the keyboard shortcut keys

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                errors = []
                if not self.hwnd:
                    self.refresh_hwnd_list()
                for hwnd in self.hwnd:
                    try:
                        get_to_home_page(hwnd)
                        break
                    except Exception as ex:
                        errors.append(str(ex))
                else:
                    logger.error('Failed to click on HOME button for errors: {err}'.format(err=errors))
            else:
                if 'firefox' in self.browser_name.lower():
                    return self.press_key_combination_on_mac_browser('key code 115 using option down')
                else:
                    return self.press_key_combination_on_mac_browser('key code 4 using {command down, shift down}')
        except Exception as ex:
            logger.error(f'Failed to press on the HOME button for error: {ex}')
            return False
        return True

    def press_esc_button(self) -> bool:
        """Attempts to press the ESC button on the keyboard

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("{ESC}", 1)
            else:
                return self.press_key_combination_on_mac_browser('key code 53 using option down')
        except Exception as ex:
            logger.error(f'Failed to press on the ESC button for error: {ex}')
            return False
        return True

    def press_enter_button(self) -> bool:
        """Attempts to press the ENTER button on the keyboard

        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("{ENTER}", 1)
            else:
                return self.press_key_combination_on_mac_browser('key code 76')
        except Exception as ex:
            logger.error(f'Failed to press on the ENTER button for error: {ex}')
            return False
        return True

    def send_keyboard_keys(self, text) -> bool:
        """Attempts to send the given text trough the keyboard
        :param text: The text to send to the browser
        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys(text, 1)
            else:
                self.press_key_combination_on_mac_browser('keystroke "{text}"'.format(text=text))
        except Exception as ex:
            logger.error(f'Failed to send keys for error: {ex}')
            return False
        return True

    def set_browser_url(self, url) -> bool:
        """Input the given url into the browser search line and press ENTER

        :param url: Text to be searched / Site url
        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                errors = []
                if not self.hwnd:
                    self.refresh_hwnd_list()
                for hwnd in self.hwnd:
                    try:
                        set_browser_url(hwnd, url)
                        break
                    except Exception as ex:
                        errors.append(str(ex))
                else:
                    logger.error('Failed to set browser url for errors: {err}'.format(err=errors))

            else:
                self.press_key_combination_on_mac_browser('key code 37 using command down')
                self.send_keyboard_keys(url)
                self.press_enter_button()

        except Exception as ex:
            logger.error(f'Failed to set the browser url for error: {ex}')
            return False
        return True

    def switch_tab(self) -> bool:
        """Attempts to switch a tab using the keyboard
        :return: True if successful
        """
        try:
            if sys.platform == 'win32':
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("^{TAB}", 1)
            else:
                return self.press_key_combination_on_mac_browser('key code 48 using control down')
        except Exception as ex:
            logger.error(f'Failed to switch tabs for error: {ex}')
            return False
        return True

    def set_focus_by_mouse_click(self):
        """Set focus on browser window by clicking on it with the mouse

        :return: True if no exception had occurred assuming success
        """
        if sys.platform == 'win32':
            self.refresh_hwnd_list()
            for i in self.get_hwnd():
                try:
                    rect = win32gui.GetWindowRect(i)  # The window (0.0.0.0) point is at the top left corner
                    start_menu_safe_zone = win32gui.GetWindowRect(win32gui.GetDesktopWindow())[3] - rect[1] - 130 > 40
                    if rect != (0, 0, 0, 0) and win32gui.IsWindowVisible(i) and start_menu_safe_zone:
                        # Avoid trying to click on background processes
                        click_on_point(i, rect[0] + 10, rect[1] + 130)
                        return True
                except Exception as ex:
                    print(ex)
                    return False
        else:
            print('Not yet implemented')
            return False

    def send_console_command(self, command: str):
        """Sends console commands to the browser using keyboard navigation"""
        shell_send_keys_replacements = {'+': '{+}', '^': '{^}', '%': '{%}', '~': '{~}', '(': '{(}', ')': '{)}',
                                        '{': '{{}', '}': '{}}', '[': '{[}', ']': '{]}'}
        if sys.platform == 'win32':
            command = ''.join([shell_send_keys_replacements.get(c, c) for c in command])
            if 'firefox' in self.browser_name:
                self.send_keyboard_keys('^+{K}')
                time.sleep(1)
                self.set_focus_by_mouse_click()
                self.send_keyboard_keys('^+{K}')
                time.sleep(1)
                self.send_keyboard_keys(command)
                time.sleep(1)
                self.press_enter_button()
                time.sleep(1)
                self.send_keyboard_keys('{F12}')
            elif 'chrome' in self.browser_name:
                self.send_keyboard_keys('^+{j}')
                time.sleep(2)
                self.send_keyboard_keys(command)
                time.sleep(1)
                self.press_enter_button()
                time.sleep(1)
                self.send_keyboard_keys('{F12}')
            else:
                raise AssertionError(f'The requested operation is not yet implemented for {self.browser_name}')
        else:
            raise AssertionError(f'The requested operation is only implemented for windows')

    def is_running(self):
        """Returns True if an instance of the browser is open"""
        if sys.platform == 'win32':
            self.refresh_hwnd_list()
            return bool(self.get_hwnd())
        else:
            return self.app_obj.is_running()

    def press_tab_button(self):
        """Using the keyboard, press the TAB button"""
        result = self.send_keyboard_keys("{TAB}") if sys.platform == 'win32' else \
            self.press_key_combination_on_mac_browser('key code 48')
        return result

    def approve_chrome_changed_assets_alert(self, tab_presses=4):
        """Using the keyboard to click on "keep changes" at chrome's "accept asset change" popup

        :param tab_presses: Number of times to press the tab key before pressing Enter. Set to 4 to support Chrome ver83
        """
        logger.debug(f'Pressing {tab_presses} "tab" an an "enter" to click on "keep changes"')
        for key_press in range(tab_presses):
            self.press_tab_button()
            time.sleep(1)  # Time for the button to register correctly in the OS
        self.press_enter_button()
        time.sleep(1)  # Time for the button to register correctly in the OS

    def open_a_new_tab(self):
        """Press the Ctrl + t combination using keyboard keys to open a new tab"""
        logger.debug('Attempting to open a new tab')
        if sys.platform == 'win32':
            self.send_keyboard_keys('^t')
        else:
            self.press_key_combination_on_mac_browser('key code 17 using command down')

    def reset_zoom_level(self):
        """Press the combination ctrl/command + '0' keyboard keys - reset zoom level to 100%"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^0')
        else:
            self.press_key_combination_on_mac_browser('key code 82 using command down')

    def decrease_zoom_level(self):
        """Press the combination ctrl/command + '-' keyboard keys - zoom out"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{-}')
        else:
            self.press_key_combination_on_mac_browser('key code 78 using command down')

    def increase_zoom_level(self):
        """Press the combination ctrl/command + '+' keyboard keys - zoom in"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{+}')
        else:
            self.press_key_combination_on_mac_browser('key code 69 using command down')

    def set_zoom_level_to_max(self):
        """Press the combination ctrl/command + '+' keyboard keys 10 times - zoom in all the way"""
        self.reset_zoom_level()
        for i in range(10):
            self.increase_zoom_level()

    def set_zoom_level_to_min(self):
        """Press the combination ctrl/command + '-' keyboard keys 10 times - zoom out all the way"""
        self.reset_zoom_level()
        for i in range(10):
            self.decrease_zoom_level()

    def press_page_down(self):
        """Press the page down key"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('{PGDN}')
        else:
            self.press_key_combination_on_mac_browser('key code 121')

    def press_page_up(self):
        """Press the page up key"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('{PGUP}')
        else:
            self.press_key_combination_on_mac_browser('key code 116')

    def press_ctrl_home(self):
        """Press the combination ctrl/command + home keyboard keys - Scroll to top of the page"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{HOME}')
        else:
            self.press_key_combination_on_mac_browser('key code 115 using command down')

    def press_ctrl_end(self):
        """Press the combination ctrl/command + end keyboard keys - Scroll to end of the page"""
        if sys.platform == 'win32':
            self.send_keyboard_keys('^{END}')
        else:
            self.press_key_combination_on_mac_browser('key code 119 using command down')
