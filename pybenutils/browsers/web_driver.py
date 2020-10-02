import os
import sys
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver


def attach_to_driver_session(session_id, executor_url, capabilities=None):
    """
    Allows to reconnect opened web driver session

    :param session_id: web driver session id
    :param executor_url: web driver url
    :param capabilities: browser capabilities
    :return: web driver which attached to open session
    """

    # Save the original function, so we can revert our patch
    org_command_execute = RemoteWebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response

            if not capabilities or capabilities['browserName'].lower() == 'chrome':
                return {'success': 0, 'value': capabilities, 'sessionId': session_id, 'status': 0}
            else:
                return {'success': 0, 'value': capabilities, 'sessionId': session_id}
        else:
            return org_command_execute(self, command, params)

    # Patch the function before creating the driver object
    RemoteWebDriver.execute = new_command_execute

    new_driver = webdriver.Remote(command_executor=executor_url, desired_capabilities=capabilities)
    new_driver.session_id = session_id
    new_driver._is_remote = False

    # Replace the patched function with original function
    RemoteWebDriver.execute = org_command_execute

    return new_driver


def close_driver(session_id, driver_url):
    """
    Close webdriver and kill its process for the safe side
    :param session_id:
    :param driver_url:
    :return:
    """
    try:
        driver_pid = None
        driver = attach_to_driver_session(session_id, driver_url)
        driver_pid = driver.service.process.pid
    except:
        pass
    finally:
        driver.quit()

    if driver_pid:
        # if run on MAC
        if sys.platform != 'win32':
            os.system('kill -9 {pid}'.format(pid=driver_pid))
        else:
            os.system('taskkill /F /PID {pid}'.format(pid=driver_pid))
