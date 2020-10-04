import sys
import time
from platform import mac_ver
from distutils.version import LooseVersion
from pybenutils.utils_logger.config_logger import get_logger
from pybenutils.os_operations.mac_input_control import mouse_drag
from pybenutils.os_operations.mac_application_control import ApplicationControl

logger = get_logger()


def handle_user_notification_center(*args):
    """Clicks OK on the UserNotificationCenter popup"""
    logger.info('Initiating handle_user_notification_center')
    user_notification_window = ApplicationControl('UserNotificationCenter')
    approve_button_titles = ["OK"]
    # approve_button_titles = ["OK", "Ignore"]
    if user_notification_window.is_running():
        for title in approve_button_titles:
            if user_notification_window.click_by_title(title, timeout=2):
                logger.info('Button {bttn} was pressed on UserNotificationCenter'.format(bttn=title))


def handle_security_agent(user_password, *args):
    """Approves the security agent popup requesting the active user's administrator password"""
    logger.info('Initiating handle_security_agent')
    security_agent_window = ApplicationControl('SecurityAgent')
    approve_button_titles = ["OK", "Modify Configuration"]
    if security_agent_window.is_running():
        if not security_agent_window.is_window_content_accessible():
            mouse_drag(370, 145, 270, 130)
        path = 'scroll area 1 of group 1 of window 1' if LooseVersion(mac_ver()[0]) < LooseVersion('10.10') else \
            'window 1'
        security_agent_window.set_element_value(element_role='text field 2', element_position_path=path,
                                                new_value=user_password)
        for title in approve_button_titles:
            if security_agent_window.click_by_title(title, timeout=2):
                logger.info(f'Button {title} was pressed on SecurityAgent')


supported_functions_dictionary = {
            'UserNotificationCenter': handle_user_notification_center,
            'SecurityAgent': handle_security_agent
        }


class PopupHandler:
    def __init__(self, services_list=('UserNotificationCenter', 'SecurityAgent'), duration_in_minutes=60,
                 administrator_password='1234', cycle_duration_in_seconds=3):
        """Approve & accept all supported popups for the given duration

        :param services_list: Services application names to monitor
        :param duration_in_minutes: Max time to keep the approval process loop alive
        :param administrator_password: The local admin user password
        :param cycle_duration_in_seconds: Time to wait between cycles of destruction and creation of subprocess
        """
        self.services_to_handle = services_list
        self.duration_in_seconds = duration_in_minutes * 60
        self.password = administrator_password
        self.time_to_wait_between_cycles = cycle_duration_in_seconds
        self.sub_process_list = []
        self.start_monitoring()

    def start_monitoring(self):
        logger.info('Initiating the start monitoring function')
        timeout = time.time() + self.duration_in_seconds
        while time.time() < timeout:
            for service_name in self.services_to_handle:
                try:
                    supported_functions_dictionary[service_name](self.password)
                except Exception as ex:
                    logger.error('{sn} ended with exception: {exm}'.format(
                        sn=supported_functions_dictionary[service_name].__name__, exm=ex))
            time.sleep(self.time_to_wait_between_cycles)


if __name__ == '__main__':
    logger.debug(sys.argv)
    PopupHandler()
