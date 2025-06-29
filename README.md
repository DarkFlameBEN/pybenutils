# pybenutils

![GitHub License](https://img.shields.io/github/license/DarkFlameBEN/pybenutils)
[![PyPI - Version](https://img.shields.io/pypi/v/pybenutils)](https://pypi.org/project/pybenutils/)
![python suggested version](https://img.shields.io/badge/python-3.12.5-red.svg)
![python minimum version](https://img.shields.io/badge/python(min)-3.10+-red.svg)
![platforms](https://img.shields.io/badge/Platforms-Linux%20|%20Windows%20|%20Mac%20-purple.svg)

## Introduction
PyBEN Utilities repository contains a variety of useful methods and classes designed to allow easy access to high-level operations 

## Getting started

### Installation
Win:
> python -m pip install pybenutils -U

macOS:
> python3 -m pip install pybenutils -U

## Modules and Classes

### AutoGUI module
PyBenAutoGui - Class to automate cross platform GUI interactions.
```
options:                                                                                                                   
  -h, --help            show this help message and exit                                                                    
  -t TITLE, --title TITLE                                                                                                  
                        Window title                                                                                       
  -a APP_PATH, --app_path APP_PATH                                                                                         
                        Application/Exe path                                                                               
  -b PYWINAUTO_BACKEND, --pywinauto_backend PYWINAUTO_BACKEND                                                              
                        A name of used back-end in Windows OS (values: "win32", "uia")                                     
  -c COMMAND, --command COMMAND                                                                                            
                        Function name to execute in the AutoGui Class                                                      
  -eh, --extra_help, --no-extra_help                                                                                       
                        Display extra help about the class and its functions (default: False)

```

> python -m pybenutils.autogui -t "Calculator" -a calc.exe -c get_object_details -b uia

> python3 -m pybenutils.autogui -t "Calculator" -a /Application/Calculator.app -c get_object_details

```
class AutoGui(builtins.object)
 |  AutoGui(title, app_path, pywinauto_backend='uia')
 |  
 |  Methods defined here:
 |  
 |  __init__(self, title, app_path, pywinauto_backend='uia')
 |      Unified interface to interact with Gui Elements
 |      
 |      :param title: Window title
 |      :param app_path: Application/Exe path
 |      :param pywinauto_backend: A name of used back-end in Windows OS (values: "win32", "uia")
 |  
 |  click_on_text(self, text: str)
 |      Clicks on text object location using pyautogui
 |  
 |  find_objects(self, text='', control_type='')
 |      Returns an iterable containing the matching object
 |      
 |      :param text: Text to search, In windows can also be the automation_id
 |      :param control_type: Filter by control type
 |      :return: An iterable containing the matching object
 |  
 |  focus_on_window(self)
 |      Focus on the app window - bring to front
 |  
 |  get_object_details(self, text='', control_type='')
 |      Returns an iterable containing dicts of matching objects properties
 |      
 |      :param text: Text to search, In windows can also be the automation_id
 |      :param control_type: Filter by control type
 |      :return: An iterable containing dicts of matching objects properties
 |  
 |  get_object_position_by_text(self, text)
 |      Return position as tuple (xl, yt, xr, yb) in windows / (x, y) in mac
```

### simple_browser_controller_cls.py
#### SimpleBrowserController
The Simple Browser Controller is a class to help directly control the host browser using keyboard inputs

Login page example:
```python
import time
from pybenutils.browsers.simple_browser_controller_cls import SimpleBrowserController

br = SimpleBrowserController('chrome')
if not br.is_running():
    br.launch()
br.set_browser_url('https://some-url')
time.sleep(5)
br.send_keys_select_all()
time.sleep(1)
br.send_keys_select_all()
br.send_keyboard_keys('username')
br.press_tab_button()
br.send_keys_select_all()
br.send_keyboard_keys('password')
br.press_enter_button()
```
#### kill_all_browsers
Closes and kills all the process sharing the given process names in the input list

#### close_all_browsers
Closes all the process sharing the given process names in the input list

### selenium_utils.py
#### get_driver(driver_name='chrome', qa_extension=False, **kwargs)
```
Returns an active web driver instance
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
```
Chrome and Firefox drivers has additional functions added in addition to the standard ones that comes from Selenium. 

New added functions:
 - get_number_open_tabs
 - is_site_displayed
 - set_selenium_log_level
 - get_logs_levels
 - gracefully_quit
 - switch_to_first_tab
 - switch_to_last_tab
 - close_secondary_tabs
 - open_new_tab
 - open_and_navigate_to_a_new_tab
 - is_scrollbar_exist
 - is_element_visible_in_viewpoint
 - wait_until_visible_by
 - click_on_xpath

ChromeDriver class new Kwargs
```
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
```

FirefoxDriver class new Kwargs
```
- option_args - [List] of arguments to be added to options (options.add_argument(x))
- log_level - [Str] Selenium and urllib3 log level (CRITICAL / FATAL / ERROR / WARNING / INFO / DEBUG / NOTSET)
- launch_attempts - [int] Permitted number of attempts to launch the selenium web driver
- only_current_dir_for_binary - [Boolean] Assume the binary HAS to be in the current working directory
```

### download_manager.py
#### download_url
```
Downloads a URL content into a file (with large file support by streaming)

:param url: URL to download_url
:param file_path: Local file name to contain the data downloaded
:param attempts: Number of attempts
:param raise_failure: Raise Exception on failure
:param verify_ssl: Verify the domain ssl
:return: New file path. Empty string if the download_url failed
```

### ssh_utils.py
#### run_commands
```
Execute the given commands trough ssh connection

 Special commands:
  - RECURSIVE-PUT file_path/folder_path [To local_path] - Copy the target from remote to local recursively
  - GET file_path/folder_path [To local_path] - Copy the target from remote to local
  - RECURSIVE-PUT file_path/folder_path TO remote_path - Sends file from local to remote recursively
  - PUT file_path/folder_path TO remote_path - Sends file from local to remote

:param server: Remote server ip
:param username: Remote server username
:param password: Remote server password
:param commands: List of commands to execute
:param stop_on_exception: Will stop executing commands if an exception occurred
:param stop_on_error: Will stop executing commands if an execution returned an stderr string
:return: List of return objects [{'ssh_stdin': str, 'ssh_stdout': str, 'ssh_stderr': str}]
```

### proxmox_utils.py
#### Proxmox class
Helper class based on Proxmoxer ProxmoxAPI making work a lot easier

Some of the included functions:
 - get_vms: Returns a full list of vms, or list with matching vms by id or name
 - clone_vms
 - migrate_vm_to_node
 - delete_vm
 - start_vm
 - stop_vm
 - snapshot handling
 - and more ...

### More functions
There are a lot of additional functions i have created over the years. Look around and find some treasures