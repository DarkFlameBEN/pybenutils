import os
import re
import sys
import time
import zipfile
import tarfile
import platform
import logging
import requests
from getpass import getuser
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from typing import List
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from selenium.webdriver.remote.remote_connection import LOGGER as SELENIUM_LOGGER
from pybenutils.network.download_manager import download_url
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


class DriverTools:
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
        body = self.find_element_by_tag_name('body')
        content = body.text
        self.set_selenium_log_level(original_log_level)
        return not [i for i in ['This site can’t be reached',
                                'Requests to the server have been blocked by an extension',
                                '404. That’s an error.\nThe requested URL was not found on this server.'] if
                    i in content]

    @staticmethod
    def set_selenium_log_level(log_level: str):
        """Sets the log level of selenium and urllib3

        :param log_level: log level (CRITICAL / FATAL / ERROR / WARNING / INFO / DEBUG / NOTSET)
        """
        SELENIUM_LOGGER.setLevel(vars(logging)[log_level.upper()])
        logging.getLogger("urllib3").setLevel(vars(logging)[log_level.upper()])

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
                logger.error('The chrome browser window was closed unexpectedly')
            self.quit()

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


class ChromeDriver(webdriver.Chrome, DriverTools):
    chrome_default_profile_path = None
    NEW_TAB_ADDRESS = 'chrome://newtab'

    def __init__(self, *args, **kwargs):
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
        ----------
         - executable_path - path to the executable. If the default is used it assumes the executable is in the $PATH
         - port - port you would like the service to run, if left as 0, a free port will be found.
         - options - this takes an instance of ChromeOptions
         - service_args - List of args to pass to the driver service
         - desired_capabilities - Dictionary object with non-browser specific
           capabilities only, such as "proxy" or "loggingPref".
         - service_log_path - Where to log information from the driver.
         - chrome_options - Deprecated argument for options
         - keep_alive - Whether to configure ChromeRemoteConnection to use HTTP keep-alive.
        """
        self.launch_attempts = kwargs.pop('launch_attempts', 2)
        self._platform_release = platform.release()

        if kwargs.get('log_level'):
            self.set_selenium_log_level(kwargs.pop('log_level', self.LOGGER_DEFAULT_LEVEL))

        self.__init_options_object(args, kwargs)

        logger.info('Launching Chrome webdriver')
        last_exception = None
        for i in range(self.launch_attempts):
            try:
                super().__init__(
                    *args,
                    **{'desired_capabilities' if self._platform_release == 'XP' else 'options': self.options},
                    **kwargs
                )
                break
            except WebDriverException as ex:
                logger.error(ex)
                last_exception = ex
                if type(ex) == SessionNotCreatedException or "executable needs to be in PATH" in str(ex):
                    self.update()
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
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
            if kwargs.pop('fullscreen', False):
                self.options.add_argument('--start-maximized')

            if kwargs.pop('headless', False):
                self.options.add_argument('--headless')

            if kwargs.pop('default_user', False):
                self.options.add_argument(f"user-data-dir={self.get_chrome_profile_path()}")

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
            local_user_name = getuser()
            if sys.platform != 'win32':  # mac
                path = f'/Users/{local_user_name}/Library/Application Support/Google/Chrome/'
            elif self._platform_release == 'XP':  # Winxp path
                path = r'C:\Documents and Settings\automation\Local Settings\Application Data\Google\Chrome\User Data'
            else:  # Win OS newer than xp
                path = f'C:\\Users\\{local_user_name}\\AppData\\Local\\Google\\Chrome\\User Data'
            self.chrome_default_profile_path = path
        return self.chrome_default_profile_path

    @staticmethod
    def update(web_drivers_folder_path=''):
        """Downloads the latest chrome webdriver

        :param web_drivers_folder_path: Leave empty to download_url to the workspace
        :return: True if downloaded successfully
        """
        # Handling output folder for the new webdriver file
        if not web_drivers_folder_path:
            web_drivers_folder_path = os.getcwd()
        if not os.path.isdir(web_drivers_folder_path):
            logger.error('The folder you are trying to download_url to does not exist. '
                         'Please create it and add it to the system path to be recognised correctly')
            return False

        # Sorting which file to download_url depending on the OS
        if sys.platform == 'win32':
            web_driver_zip_file_name = 'chromedriver_win32.zip'
        elif sys.platform == 'darwin':
            web_driver_zip_file_name = 'chromedriver_mac64.zip'
        else:
            web_driver_zip_file_name = 'chromedriver_linux64.zip'

        logger.info('Getting chrome driver latest stable version number from api')
        for i in range(3):
            try:
                response = requests.get('http://chromedriver.storage.googleapis.com/LATEST_RELEASE')
                if response.status_code < 400:
                    latest_version = response.content.decode()
                    break
                else:
                    logger.warning(f'Response status code: {response.status_code}')
            except Exception as ex:
                logger.error(ex)
        else:
            return False

        logger.info(f'Downloading chrome driver version: {latest_version}')
        download_url(f'http://chromedriver.storage.googleapis.com/{latest_version}/{web_driver_zip_file_name}')

        logger.info(f'Extracting {web_driver_zip_file_name} to {web_drivers_folder_path}')
        with zipfile.ZipFile(web_driver_zip_file_name, 'r') as zip_ref:
            zip_ref.extractall(web_drivers_folder_path)

        logger.info('Webdriver deployed successfully')
        return True


class FirefoxDriver(webdriver.Firefox, DriverTools):
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
        -----------
         - firefox_profile - Instance of ``FirefoxProfile`` object or a string.
           If undefined, a fresh profile will be created in a temporary location on the system.
         - firefox_binary - Instance of ``FirefoxBinary`` or full path to the Firefox binary.
           If undefined, the system default Firefox installation will  be used.
         - timeout - Time to wait for Firefox to launch when using the extension connection.
         - capabilities - Dictionary of desired capabilities.
         - proxy - The proxy settings to us when communicating with Firefox via the extension connection.
         - executable_path - Full path to override which geckodriver binary to use for Firefox 47.0.1 and greater,
           which defaults to picking up the binary from the system path.
         - options - Instance of ``options.Options``.
         - service_log_path - Where to log information from the driver.
         - firefox_options - Deprecated argument for options
         - service_args - List of args to pass to the driver service
         - desired_capabilities - alias of capabilities. In future versions of this library,
           this will replace 'capabilities'. This will make the signature consistent with RemoteWebDriver.
         - log_path - Deprecated argument for service_log_path
         - keep_alive - Whether to configure remote_connection.RemoteConnection to use HTTP keep-alive.
        """
        self.launch_attempts = kwargs.pop('launch_attempts', 2)
        self._platform_release = platform.release()

        if kwargs.get('log_level'):
            self.set_selenium_log_level(kwargs.pop('log_level', self.LOGGER_DEFAULT_LEVEL))

        self.options = kwargs.pop('options', webdriver.FirefoxOptions())

        for arg in kwargs.pop('option_args', []):
            self.options.add_argument(arg)

        logger.info('Launching Chrome webdriver')
        last_exception = None
        for i in range(self.launch_attempts):
            try:
                super().__init__(
                    *args,
                    **{'desired_capabilities' if self._platform_release == 'XP' else 'options': self.options},
                    **kwargs
                )
                break
            except WebDriverException as ex:
                logger.error(ex)
                last_exception = ex
                if type(ex) == SessionNotCreatedException or "executable needs to be in PATH" in str(ex):
                    self.update()
            except Exception as ex:
                logger.error(ex)
                last_exception = ex
        else:
            raise last_exception
        logger.info('Firefox webdriver launched successfully')

    @staticmethod
    def update(web_drivers_folder_path=''):
        """Downloads the latest gecko (firefox) webdriver

        :param web_drivers_folder_path: Leave empty to download_url to the workspace
        :return: True if downloaded successfully
        """
        if not web_drivers_folder_path:
            web_drivers_folder_path = os.getcwd()
        if not os.path.isdir(web_drivers_folder_path):
            logger.error('The folder you are trying to download_url to does not exist. '
                         'Please create it and add it to the system path to be recognised correctly')
            return False

        # Creating a list of archive files appearing in this page to get the latest webdriver archive file name.
        response = requests.get('https://github.com/mozilla/geckodriver/releases')
        body = response.content.decode()
        archives = []
        for i in body.splitlines():
            match = re.search('>(geckodriver-v.*)<', i)
            if match:
                archives.append(match.group(1))

        if sys.platform == 'win32':
            os_keyword = 'win{os_bit_count}'.format(
                os_bit_count='64' if os.path.exists(r'C:\Program Files (x86)') else '32')
        elif sys.platform == 'darwin':
            os_keyword = 'mac'
        else:
            os_keyword = 'linux64'

        for file_name in archives:
            if os_keyword in file_name:
                installer_file_name = file_name
                installer_path = f'http://github.com/mozilla/geckodriver/releases/download/' \
                                 f'{file_name.split("-")[1]}/{file_name}'
                break
        else:
            logger.error('Failed to extract the appropriate web driver from the github gecko driver page')
            return False

        if not download_url(installer_path, raise_failure=False):
            return False

        file_ext = os.path.splitext(installer_file_name)[-1]
        if file_ext == '.zip':
            logger.info(f'Extracting {installer_file_name} to {web_drivers_folder_path}')
            with zipfile.ZipFile(installer_file_name, 'r') as zip_ref:
                zip_ref.extractall(web_drivers_folder_path)
        elif file_ext == '.gz':
            with tarfile.open(installer_file_name, "r:gz") as tar:
                tar.extractall(web_drivers_folder_path)
        elif file_ext == '.tar':
            with tarfile.open(installer_file_name, "r:") as tar:
                tar.extractall(web_drivers_folder_path)
        else:
            logger.error(f'Extraction method for file {installer_file_name} is not implemented')
            return False

        logger.info('Webdriver deployed successfully')
        return True


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
        driver.find_element_by_tag_name('body').screenshot(file_path)  # avoids scrollbar
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
