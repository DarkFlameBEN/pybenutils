import logging
import os
import pathlib
import platform
import re
import subprocess
import sys
import time
from typing import List

import psutil
from appium.webdriver import Remote
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.remote_connection import LOGGER as SELENIUM_LOGGER
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from pybenutils.browsers.simple_browser_controller_cls import kill_all_browsers
from pybenutils.os_operations.process import kill_process_by_cmd
from pybenutils.utils_logger.config_logger import get_logger
from pybenutils.windows_registry import get_registry_value

logger = get_logger()


chromedriver_name = 'chromedriver.exe' if sys.platform == 'win32' else 'chromedriver'
chrome_name = 'chrome.exe' if sys.platform == 'win32' else "Google Chrome"


def get_driver(driver_name='chrome', qa_extension=False, **kwargs):
    """Returns an active web driver instance

    :param driver_name: name of the driver:
      - chrome (selenium)
      - firefox (selenium)
      - safari (selenium)
      - headless_chrome (selenium)
      - edge (selenium)
      - ios_x - Example: ios_chrome (Appium)
      - android_x - Example: android_chrome (Appium)
    :param qa_extension: Whether to use qa extension
    :return: web driver object (Selenium / Appium based)
    """
    extra_param = {}
    if driver_name.lower() == 'chrome':
        return ChromeDriver(qa_extension=qa_extension, **extra_param, **kwargs)
    if driver_name.lower() == 'headless_chrome':
        return ChromeDriver(headless=True, **extra_param, **kwargs)
    elif driver_name.lower() == 'firefox':
        return FirefoxDriver(**extra_param, **kwargs)
    if driver_name.lower() == 'edge':
        return ChromiumEdgeDriver(**extra_param, **kwargs)
    elif driver_name.lower() == 'safari':
        return SafariDriver(**kwargs)
    elif driver_name.startswith('android') or driver_name.startswith('ios'):
        return AppiumDriver(driver_name, **kwargs)
    else:
        raise Exception(f'Wrong or not supported driver name passed: "{driver_name}"')


def get_chrome_version():
    """Return Google Chrome version"""
    major_version = ''
    if sys.platform == 'win32':
        # https://stackoverflow.com/questions/50880917/how-to-get-chrome-version-using-command-prompt-in-windows
        try:
            chrome_version = get_registry_value('HKEY_CURRENT_USER', r'Software\Google\Chrome\BLBeacon', 'version')
            major_version = chrome_version.split('.')[0]
        except Exception as err:
            logger.exception(err)
    else:
        # https://stackoverflow.com/questions/44612147/how-to-find-the-chrome-browser-version-using-terminal-in-mac
        try:
            cmd = r'/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version'
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)
            chrome_version = res.stdout
            if chrome_version:
                res = re.search(r'Google Chrome (\d+)\..*', chrome_version)
                if res:
                    major_version = res.group(1)
        except Exception as err:
            logger.exception(err)
    return major_version


def get_edge_chromium_version():
    """Return Chromium Edge version"""
    edge_version = ''
    if sys.platform == 'win32':
        # https://stackoverflow.com/a/62680159
        try:
            edge_version = get_registry_value('HKEY_CURRENT_USER', r'Software\Microsoft\Edge\BLBeacon', 'version')

        except Exception as err:
            logger.exception(err)
    else:
        # https://stackoverflow.com/questions/44612147/how-to-find-the-chrome-browser-version-using-terminal-in-mac
        try:
            cmd = r'/Applications/Microsoft\ Edge.app/Contents/MacOS/Microsoft\ Edge --version'
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)
            edge_version = res.stdout
            if edge_version:
                res = re.search(r'Microsoft Edge (\d+\.\d+\.\d+\.\d+).*', edge_version)
                if res:
                    edge_version = res.group(1)
        except Exception as err:
            logger.exception(err)
    return edge_version


class _DriverTools:
    """Meant to be inherited by webdriver sub-classes to add general tools and tricks, can be used on all browsers"""

    LOGGER_DEFAULT_LEVEL = 'DEBUG'

    def __bool__(self):
        """Returns True only if there are open browser windows / tabs"""
        return bool(self.get_number_open_tabs())
    # noinspection PyBroadException

    def get_number_open_tabs(self):
        """Returns the number of open browser windows and tabs"""
        try:
            return len(self.window_handles)
        except Exception:
            return 0

    def is_site_displayed(self) -> bool:
        """Returns True if the current page is displaying a web-page (page might not be fully loaded)"""
        if not self:
            return False
        original_log_level = self.get_logs_levels().get('selenium', self.LOGGER_DEFAULT_LEVEL)
        self.set_selenium_log_level('WARNING')
        if 'about:blank' in str(self.current_url):
            return False
        body = self.find_element(By.TAG_NAME, 'body')
        content = body.text
        self.set_selenium_log_level(original_log_level)
        return not [i for i in ['This site can\'t be reached',
                                'Requests to the server have been blocked by an extension',
                                '404. That\'s an error.\nThe requested URL was not found on this server.'] if
                    i in content]

    @staticmethod
    def set_selenium_log_level(log_level: str):
        """Sets the log level of selenium and urllib3

        :param log_level: log level (CRITICAL / FATAL / ERROR / WARNING / INFO / DEBUG / NOTSET)
        """
        try:
            SELENIUM_LOGGER.setLevel(vars(logging)[log_level.upper()])
            logging.getLogger("urllib3").setLevel(vars(logging)[log_level.upper()])
        except KeyError as ex:
            logger.error(f'Encountered an error while trying to set log level: {ex}')
            for known_log_level in ['DEBUG', 'INFO', 'ERROR', 'WARNING', 'NOTSET', 'FATAL', 'CRITICAL']:
                # This is a fix to support custom unknown log levels
                if log_level.upper().startswith(known_log_level):
                    SELENIUM_LOGGER.setLevel(vars(logging)[known_log_level])
                    logging.getLogger("urllib3").setLevel(vars(logging)[known_log_level])
                    break
            else:
                logger.error('Failed to detect any relation to a known log level. Defaulting to DEBUG')
                known_log_level = 'DEBUG'
                SELENIUM_LOGGER.setLevel(vars(logging)[known_log_level])
                logging.getLogger("urllib3").setLevel(vars(logging)[known_log_level])

    @staticmethod
    def get_logs_levels():
        """Returns a dict of the current log levels.

        {'selenium': selenium_log_level, 'urllib3': urllib3_log_level, 'main_logger': utils_log_level}
        """
        selenium_log_level = logging._levelToName.get(SELENIUM_LOGGER.getEffectiveLevel())
        urllib3_log_level = logging._levelToName.get(logging.getLogger("urllib3").getEffectiveLevel())
        utils_log_level = logging._levelToName.get(logger.getEffectiveLevel())
        return {'selenium': selenium_log_level,
                'urllib3': urllib3_log_level,
                'main_logger': utils_log_level}

    def gracefully_quit(self):
        """Closing the chrome web driver window, than quitting the webdriver

          - Support for missing Chrome window
          - Support for missing driver object
        """
        if self:
            logger.debug('Closing driver')
            try:
                self.close()
            except WebDriverException:
                logger.error('The browser window was closed unexpectedly')
            try:
                self.quit()
            except WebDriverException:
                logger.warning('The quit command failed on exception. Its possible the browser already closed.')

    def switch_to_first_tab(self):
        """Switches to control the first tab or window opened"""
        self._switch_to.window(self.window_handles[0])

    def switch_to_last_tab(self):
        """Switches to control the last tab or window opened"""
        self._switch_to.window(self.window_handles[-1])

    def close_secondary_tabs(self):
        """Closes all tabs except the first one in the webdriver window"""
        while len(self.window_handles) > 1:
            self.switch_to_last_tab()
            self.close()
        self.switch_to_first_tab()

    def open_new_tab(self, url=''):
        """Attempting to open a new tab with the given URL.

        :param url: URL to open in a new tab. Leave empty for new tab with about:blank
        """
        self.execute_script(f'window.open("{url}")')

    def open_and_navigate_to_a_new_tab(self):
        """Opens a new tab, switched to it and navigates to the new tab address"""
        self.open_new_tab()
        self.switch_to_last_tab()
        self.get(self.NEW_TAB_ADDRESS)

    def is_scrollbar_exist(self):
        """Returns True if the current web page main window has a vertical scrollbar (Not checking inner elements)"""
        return self.execute_script(
            'return document.documentElement.scrollHeight > document.documentElement.clientHeight;')

    def is_element_visible_in_viewpoint(self, element) -> bool:
        """Return True if the given element is showing the user view point (can be seen on the screen)"""
        # Calculates the elements position relative position against the user current point of view (see on screen)
        # Element.is_visible() will return True even if the element is not currently in the user view point
        return self.execute_script("var elem = arguments[0],                 "
                                   "  box = elem.getBoundingClientRect(),    "
                                   "  cx = box.left + box.width / 2,         "
                                   "  cy = box.top + box.height / 2,         "
                                   "  e = document.elementFromPoint(cx, cy); "
                                   "for (; e; e = e.parentElement) {         "
                                   "  if (e === elem)                        "
                                   "    return true;                         "
                                   "}                                        "
                                   "return false;                            "
                                   , element)

    def wait_until_visible_by(self, by: By, value, wait_time=10):
        """Returns True if the element was found by the driver within the time limit (seconds)

        :param by: By object like By.XPATH
        :param value: The searched value
        :param wait_time: Time limit in seconds
        :return: True if the element was found
        """
        try:
            WebDriverWait(self, wait_time).until(
                expected_conditions.visibility_of_element_located((by, value)))
            return True
        except TimeoutException:
            return False

    def wait_until_xpath_visible(self, xpath: str, wait_time=10):
        """Returns True if the element was found by the driver within the time limit (seconds)

        :param xpath: Element xpath string
        :param wait_time: Time to wait for the object to be visible (seconds)
        :return: True if visible
        """
        return self.wait_until_visible_by(By.XPATH, xpath, wait_time)
    def click_on_xpath(self, xpath: str, wait_time=10):
        """Tries to locate the given xpath and click on it. Returns True if successful

        :param xpath: Element xpath string
        :param wait_time: Time to wait for the object to be visible (seconds)
        :return: True if successful
        """
        if not self.wait_until_xpath_visible(xpath, wait_time=wait_time):
            return False
        self.find_element(By.XPATH, xpath).click()
        return True




class ChromeDriver(webdriver.Chrome, _DriverTools):
    chrome_default_profile_path = None
    NEW_TAB_ADDRESS = 'chrome://newtab'

    def __init__(self, qa_extension=False, *args, **kwargs):
        """
        Creates a new instance of the chrome driver.
        Starts the service and then creates new instance of chrome driver.

         - default_user - [Boolean] Use the default Chrome user installed on the OS (user-data-dir)
         - fullscreen - [Boolean] Open window at fullscreen (--start-maximized)
         - excludeSwitches - [List] of switches to exclude (options.add_experimental_option("excludeSwitches", [x]))
         - crx_path - [Str] Open with extension pre-installed (options.add_extension)
         - option_args - [List] of arguments to be added to options (options.add_argument(x))
         - log_level - [Str] Selenium and urllib3 log level (CRITICAL / FATAL / ERROR / WARNING / INFO / DEBUG / NOTSET)
         - launch_attempts - [int] Permitted number of attempts to launch the selenium web driver
         - headless - [Boolean] Open the Chrome instance without visible gui (--headless)
         - incognito - [Boolean] Open the Chrome instance in incognito mode
         - only_current_dir_for_binary - [Boolean] Assume the binary HAS to be in the current working directory
        ----------
         - executable_path - Deprecated: path to the executable. If the default is used it assumes the executable is in the $PATH
         - port - Deprecated: port you would like the service to run, if left as 0, a free port will be found.
         - options - this takes an instance of ChromeOptions
         - service - Service object for handling the browser driver if you need to pass extra details
         - service_args - Deprecated: List of args to pass to the driver service
         - desired_capabilities - Deprecated: Dictionary object with non-browser specific
           capabilities only, such as "proxy" or "loggingPref".
         - service_log_path - Deprecated: Where to log information from the driver.
         - keep_alive - Deprecated: Whether to configure ChromeRemoteConnection to use HTTP keep-alive.
        """
        self.launch_attempts = kwargs.pop('launch_attempts', 3)
        self._platform_release = platform.release()

        if kwargs.get('log_level'):
            self.set_selenium_log_level(kwargs.pop('log_level', self.LOGGER_DEFAULT_LEVEL))

        self.__init_options_object(args, kwargs)

        if kwargs.pop('only_current_dir_for_binary', False):
            chromedriver_location = os.path.join(os.getcwd(), 'chromedriver{ext}'.format(
                ext=".exe" if sys.platform == "win32" else ""))
        else:
            chromedriver_location = None
        service_obj = Service(chromedriver_location) if chromedriver_location else None

        logger.info('Launching Chrome webdriver')
        last_exception = None
        for i in range(self.launch_attempts):
            if i > 0:
                time.sleep(10)  # time for the browsers to update if they need too
            try:
                service_dict = {}
                if service_obj:
                    service_dict.update({'service': service_obj})
                super().__init__(
                    *args,
                    **{'desired_caplities' if self._platform_release == 'XP' else 'options': self.options},
                    **service_dict,
                    **kwargs
                )
                break
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
                kill_all_browsers('chrome')
                time.sleep(1)
        else:
            raise last_exception
        logger.info('Chrome webdriver launched successfully')

    def __init_options_object(self, args, kwargs):
        """Handles the creation of Chrome options object"""
        if self._platform_release == 'XP':
            self.options = kwargs.pop('options', {"chromeOptions": {
                "args": [self.get_chrome_profile_path()],
                "excludeSwitches": ["disable-default-apps", "restore-last-session", "disable-web-resources"]}})

            if kwargs.pop('default_user', False):
                self.options['chromeOptions']['args'] = [self.get_chrome_profile_path()]

        else:
            self.options = kwargs.pop('options', webdriver.ChromeOptions())
            if sys.platform == 'darwin':
                self.options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

            if kwargs.pop('fullscreen', False):
                self.options.add_argument('--start-maximized')

            if kwargs.pop('headless', False):
                self.options.add_argument('--headless')

            if kwargs.pop('incognito', False):
                self.options.add_argument('--incognito')

            if kwargs.pop('default_user', False):
                self.options.add_argument(f"user-data-dir={self.get_chrome_profile_path()}")
            else:  # Only if anonymous window
                prefs = {"download.default_directory": f'{os.getcwd()}{os.sep}'}  # IMPORTANT - ENDING SLASH V IMPORTANT
                self.options.add_experimental_option("prefs", prefs)

            if kwargs.get('excludeSwitches'):
                switches_to_exclude = kwargs.pop('excludeSwitches', [])
                self.options.add_experimental_option("excludeSwitches", switches_to_exclude)

            if kwargs.get('crx_path'):
                self.options.add_extension(kwargs.pop('crx_path', ''))

            for arg in kwargs.pop('option_args', []):
                self.options.add_argument(arg)
        return self.options

    def get_chrome_profile_path(self) -> str:
        """Returns the chrome default profile path"""
        if not self.chrome_default_profile_path:
            if self._platform_release == 'XP':  # Winxp path
                path = r'C:\Documents and Settings\automation\Local Settings\Application Data\Google\Chrome\User Data'
            elif sys.platform == 'win32': # Win OS newer than xp
                path = f'{str(pathlib.Path.home())}\\AppData\\Local\\Google\\Chrome\\User Data'
            elif sys.platform == 'darwin':  # Mac path
                path = f'{str(pathlib.Path.home())}/Library/Application Support/Google/Chrome/'
            else:  # Ubuntu
                path = f'{str(pathlib.Path.home())}/.config/google-chrome'
            self.chrome_default_profile_path = path
        return self.chrome_default_profile_path


class FirefoxDriver(webdriver.Firefox, _DriverTools):
    NEW_TAB_ADDRESS = 'about:newtab'

    def __init__(self, *args, **kwargs):
        """Starts a new local session of Firefox.

        Based on the combination and specificity of the various keyword arguments,
        a capabilities dictionary will be constructed that is passed to the remote end.

        The keyword arguments given to this constructor are helpers to more easily allow Firefox WebDriver sessions
        to be customised with different options.  They are mapped on to a capabilities dictionary that is passed on
        to the remote end.

        As some of the options, such as `firefox_profile` and `options.profile` are mutually exclusive,
        precedence is given from how specific the setting is.  `capabilities` is the least specific keyword argument,
        followed by `options`, followed by `firefox_binary` and `firefox_profile`.

        In practice this means that if `firefox_profile` and `options.profile` are both set,
        the selected profile instance will always come from the most specific variable.
        In this case that would be `firefox_profile`.  This will result in `options.profile` to be ignored because it
        is considered a less specific setting than the top-level `firefox_profile` keyword argument.
        Similarly, if you had specified a `capabilities["moz:firefoxOptions"]["profile"]` Base64 string,
        this would rank below `options.profile`.

         - option_args - [List] of arguments to be added to options (options.add_argument(x))
         - log_level - [Str] Selenium and urllib3 log level (CRITICAL / FATAL / ERROR / WARNING / INFO / DEBUG / NOTSET)
         - launch_attempts - [int] Permitted number of attempts to launch the selenium web driver
         - only_current_dir_for_binary - [Boolean] Assume the binary HAS to be in the current working directory
        -----------
         - firefox_profile - IDeprecated: Instance of ``FirefoxProfile`` object or a string.
          If undefined, a fresh profile will be created in a temporary location on the system.
         - firefox_binary - Deprecated: Instance of ``FirefoxBinary`` or full path to the Firefox binary.
           If undefined, the system default Firefox installation will  be used.
         - capabilities - Deprecated: Dictionary of desired capabilities.
         - proxy -Deprecated - The proxy settings to use when communicating with Firefox via the extension connection.
         - executable_path - Deprecated: Full path to override which geckodriver binary to use for Firefox 47.0.1
          and greater, which defaults to picking up the binary from the system path.
         - options - Instance of ``options.Options``.
         - service - (Optional) service instance for managing the starting and stopping of the driver.
         - service_log_path - Deprecated: Where to log information from the driver.
         - service_args - Deprecated: List of args to pass to the driver service
         - desired_capabilities - Deprecated: alias of capabilities. In future versions of this library,
         this will replace 'capabilities'. This will make the signature consistent with RemoteWebDriver.
         - keep_alive - Whether to configure remote_connection.RemoteConnection to use HTTP keep-alive.
        """
        self.launch_attempts = kwargs.pop('launch_attempts', 3)
        self._platform_release = platform.release()

        if kwargs.get('log_level'):
            self.set_selenium_log_level(kwargs.pop('log_level', self.LOGGER_DEFAULT_LEVEL))

        self.options = kwargs.pop('options', webdriver.FirefoxOptions())

        for arg in kwargs.pop('option_args', []):
            self.options.add_argument(arg)

        if kwargs.pop('only_current_dir_for_binary', False):
            binary_location = os.path.join(os.getcwd(), 'geckodriver{ext}'.format(
                ext=".exe" if sys.platform == "win32" else ""))
        else:
            binary_location = None
        service_obj = FirefoxService(binary_location)

        logger.info('Launching Firefox webdriver')
        last_exception = None
        for i in range(self.launch_attempts):
            if i > 0:
                time.sleep(10)  # time for the browsers to update if they need too
            try:
                super().__init__(
                    *args,
                    **{'desired_capabilities' if self._platform_release == 'XP' else 'options': self.options,
                       'service': service_obj},
                    **kwargs
                )
                break
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
                kill_all_browsers('firefox')
                time.sleep(1)
        else:
            raise last_exception
        logger.info('Firefox webdriver launched successfully')


def full_page_image(url, file_path, page_load_time=5):
    """Opens the given url in a headless Chrome instance and takes a full page body image

    :param url: Page URL to load and image
    :param file_path: Image path. Has to be .png file. Existing file will be overwritten
    :param page_load_time: Time to delay between navigation and screenshot attempt
    """
    driver = ChromeDriver(headless=True, fullscreen=True)
    try:
        driver.get(url)
        time.sleep(page_load_time)
        # Ref: https://stackoverflow.com/a/52572919/
        required_width = driver.execute_script('return document.body.parentNode.scrollWidth')
        required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
        driver.set_window_size(required_width, required_height)
        # driver.save_screenshot(path)  # has scrollbar
        driver.find_element(By.TAG_NAME, 'body').screenshot(file_path)  # avoids scrollbar
    finally:
        if driver:
            driver.quit()


def chrome_app_store_full_page_screenshots(driver, base_image_path: str) -> List[str]:
    """Uses page down to take several screenshots of an entire google chrome app store page

    :param driver: Selenium webdriver live instance (Already on page)
    :param base_image_path: File path to save the new image. Only support .png files. Existing file will be overwritten.
     Final path will be <base_image_path>01.png, <base_image_path>02.png etc...
    :return: List of saved images
    """
    saved_images = []  # To store the saved image

    # File type restriction comes from the driver implementation. Only .png file type supported
    base_image_path = f'{os.path.splitext(base_image_path)[0]}.png'
    # Scroll to top of the page
    actions = ActionChains(driver)
    actions.send_keys(Keys.HOME).perform()
    # Finds the second "Add to chrome" button as a marker to the end of the page
    second_add_to_chrome_button = driver.find_elements_by_xpath("//*[text()='Add to Chrome']")[1]

    # Loops page down and saving screenshots of the page
    for i in range(1, 20):  # Assuming the page will not be longer than 20 page downs length and ensures an exit point
        image_path = f'{base_image_path[:-4:]}{i:02}.png'
        driver.get_screenshot_as_file(image_path)
        saved_images.append(image_path)
        if driver.is_element_visible_in_viewpoint(second_add_to_chrome_button):
            break  # Assuming we reached the end of the page if we see the second "Add to chrome" button
        actions.send_keys(Keys.PAGE_DOWN).perform()

    return saved_images  # Returns the list of taken images


appium_presets = {
    'android_chrome': {
        'platformName': 'Android',
        'platformVersion': '11',
        'automationName': 'uiautomator2',
        'deviceName': 'Android_Device',
        'browserName': 'Chrome',
        'userProfile': '11',
        'noReset': True
    },
    'android_play_store': {
        'platformName': 'Android',
        'platformVersion': '11',
        'automationName': 'uiautomator2',
        'deviceName': 'Android_Device',
        'newCommandTimeout': '90',
        'appPackage': 'com.android.vending',
        'appActivity': 'com.android.vending.AssetBrowserActivity',
        'noReset': True
    },
    'ios_safari': {
        "udid": 'auto',
        "platformName": "iOS",
        "platformVersion": "14.3",
        "deviceName": "iPhone",
        "automationName": "XCUITest",
        "browserName": "safari",
        "startIWDP": True
    },
    'ios_settings': {
        "udid": 'auto',
        "platformName": "iOS",
        "platformVersion": "14.4",
        "deviceName": "iPhone",
        "automationName": "XCUITest",
        "startIWDP": True,
        'app': "com.apple.Preferences",
        'safariInitialUrl': 'https://www.google.com',
        'newCommandTimeout': '90',
        'alias': 'settings'
    },
    'ios_testflight': {
        "udid": 'auto',
        "platformName": "iOS",
        "platformVersion": "14.3",
        "deviceName": "iPhone",
        "automationName": "XCUITest",
        "startIWDP": True,
        'app': 'com.apple.TestFlight',
        'newCommandTimeout': '90',
        'alias': 'main'
    }
}


class AppiumDriver(Remote, _DriverTools):
    """Create a new driver that will issue commands using the wire protocol.

     - launch_attempts - [int] Permitted number of attempts to launch the selenium web driver
     -----------
     - command_executor - Either a string representing URL of the remote server or a custom
         remote_connection.RemoteConnection object. Defaults to 'http://127.0.0.1:4444/wd/hub'.
     - desired_capabilities - A dictionary of capabilities to request when
         starting the browser session. Required parameter.
     - browser_profile - A selenium.webdriver.firefox.firefox_profile.FirefoxProfile object.
         Only used if Firefox is requested. Optional.
     - proxy - A selenium.webdriver.common.proxy.Proxy object. The browser session will
         be started with given proxy settings, if possible. Optional.
     - keep_alive - Whether to configure remote_connection.RemoteConnection to use
         HTTP keep-alive. Defaults to False.
     - file_detector - Pass custom file detector object during instantiation. If None,
         then default LocalFileDetector() will be used.
     - options - instance of a driver options.Options class
    """
    def __init__(self, preset_name='android_chrome', command_executor='http://localhost:4723/wd/hub', *args, **kwargs):
        if command_executor:  # This will be used for starting the appium server automatically
            self.host = command_executor.split('http://', 1)[-1].split('/', 1)[0].split(':', 1)[0]
            self.port = command_executor.split(self.host, 1)[-1].split(':', 1)[-1].split('/', 1)[0]
        else:
            self.host = '127.0.0.1'
            self.port = '4444'
        self.launch_attempts = kwargs.pop('launch_attempts', 2)
        self.dc = kwargs.pop('desired_capabilities', appium_presets.get(preset_name, None))
        if not self.dc:
            raise Exception(f'No supported input Capabilities detected. Capabilities: {self.dc}, '
                            f'Preset: {preset_name}')

        logger.info('Launching Appium remote webdriver')
        last_exception = None
        for i in range(self.launch_attempts):
            try:
                super().__init__(command_executor=command_executor, desired_capabilities=self.dc, *args, **kwargs)
                break
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
                if "No connection could be made because the target machine actively refused it" in str(ex) or\
                        "[Errno 61] Connection refused" in str(ex):
                    try:
                        self.start_appium_server(host=self.host, port=self.port)
                    except Exception as ex:
                        logger.error(ex)
                        last_exception = ex

        else:
            raise last_exception
        logger.info('Appium remote webdriver launched successfully')
        time.sleep(2)

    @staticmethod
    def start_appium_server(host='localhost', port='4723', ignore_stdout=True):
        """Starts the appium server via command line. Will skip if the server is already running

        :param host: Host domain / ip for the appium server
        :param port: Connection port
        :param ignore_stdout: Filter out the subprocess stdout. Will not print the server output. cleans the log.
        :return:
        """
        if AppiumDriver.is_appium_server_live():
            logger.info('Appium server already live')
            return
        args = {'stdout': subprocess.DEVNULL, 'stderr': subprocess.STDOUT} if ignore_stdout else {}
        p = subprocess.Popen(
            f'appium -a {host} -p {port} --allow-insecure chromedriver_autodownload --allow-insecure=adb_shell', shell=True, **args)
        time.sleep(5)
        if p.returncode:
            p.communicate()
            logger.info(p.stdout)
            logger.error(p.stderr)
        if not AppiumDriver.is_appium_server_live():
            raise Exception('Failed to initiate appium driver')

    @staticmethod
    def stop_appium_server():
        """kills the appium server processes via command line"""
        if AppiumDriver.is_appium_server_live():
            kill_process_by_cmd('appium', kill_all_instances=True, kill_children=True)
            time.sleep(1)

    @staticmethod
    def is_appium_server_live():
        """Returns True if the appium server is currently running"""
        for p in psutil.process_iter():
            try:
                condition_result = 'appium' in ' '.join(p.cmdline())
            except Exception as ex:
                continue

            if condition_result:
                return True
        return False

    def gracefully_quit(self):
        super().gracefully_quit()
        self.stop_appium_server()


class SafariDriver(webdriver.Safari, _DriverTools):
    NEW_TAB_ADDRESS = ''

    def __init__(self, *args, **kwargs):
        """Creates a new Safari driver instance and launches or finds a running safaridriver service.

        :Args:
         - port - The port on which the safaridriver service should listen for new connections. If zero, a free port will be found.
         - executable_path - Path to a custom safaridriver executable to be used. If absent, /usr/bin/safaridriver is used.
         - reuse_service - If True, do not spawn a safaridriver instance; instead, connect to an already-running service that was launched externally.
         - desired_capabilities: Dictionary object with desired capabilities (Can be used to provide various Safari switches).
         - quiet - If True, the driver's stdout and stderr is suppressed.
         - keep_alive - Whether to configure SafariRemoteConnection to use
             HTTP keep-alive. Defaults to False.
         - service_args : List of args to pass to the safaridriver service
        """
        self.launch_attempts = kwargs.pop('launch_attempts', 2)
        last_exception = None
        for i in range(self.launch_attempts):
            try:
                super().__init__(*args, **kwargs)
                break
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
                kill_all_browsers('safari')
                time.sleep(1)
        else:
            raise last_exception


class ChromiumEdgeDriver(webdriver.Edge, _DriverTools):
    NEW_TAB_ADDRESS = ''

    def __init__(self, *args, **kwargs):
        """
        Creates a new instance of the edge driver.
        Starts the service and then creates new instance of edge driver.

        :Args:
         - executable_path - Deprecated: path to the executable. If the default is used it assumes the executable is in the $PATH
         - port - Deprecated: port you would like the service to run, if left as 0, a free port will be found.
         - options - this takes an instance of EdgeOptions
         - service_args - Deprecated: List of args to pass to the driver service
         - capabilities - Deprecated: Dictionary object with non-browser specific
           capabilities only, such as "proxy" or "loggingPref".
         - service_log_path - Deprecated: Where to log information from the driver.
         - service - Service object for handling the browser driver if you need to pass extra details
         - keep_alive - Whether to configure EdgeRemoteConnection to use HTTP keep-alive.
         - verbose - whether to set verbose logging in the service.
         """
        self.launch_attempts = kwargs.pop('launch_attempts', 2)
        last_exception = None

        self.options = kwargs.pop('options', webdriver.EdgeOptions())

        for arg in kwargs.pop('option_args', []):
            self.options.add_argument(arg)

        if kwargs.pop('only_current_dir_for_binary', False):
            binary_location = os.path.join(os.getcwd(), 'msedgedriver{ext}'.format(
                ext=".exe" if sys.platform == "win32" else ""))
        else:
            binary_location = None
        service_obj = EdgeService(binary_location)

        logger.info('Launching Chromium Edge webdriver')
        for i in range(self.launch_attempts):
            try:
                super().__init__(*args, **{'options': self.options, 'service': service_obj}, **kwargs)
                break
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
                kill_all_browsers('msedge')
                time.sleep(1)
        else:
            raise last_exception
