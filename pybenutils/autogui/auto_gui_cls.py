import re
import pyautogui
import sys
from pybenutils.os_operations.mac_application_control import ApplicationControl
from pybenutils.os_operations.mac_operations import run_apple_script
from pybenutils.utils_logger.config_logger import get_logger
if sys.platform == 'win32':
    from pywinauto import application
    from pywinauto.timings import TimeoutError as pywinautoTimeoutError

logger = get_logger()


class AutoGui:
    def __init__(self, title, app_path, pywinauto_backend='uia'):
        """Unified interface to interact with Gui Elements

        :param title: Window title
        :param app_path: Application/Exe path
        :param pywinauto_backend: A name of used back-end in Windows OS (values: "win32", "uia")
        """
        self.title = title
        self.app_path = app_path
        if sys.platform == 'win32':
            self.app = application.Application(backend=pywinauto_backend)
            try:
                self.app.connect(title=self.title, timeout=10)
            except pywinautoTimeoutError:
                logger.debug('Failed to connect to a live window. Will start a new instance')
                self.app.start(self.app_path)
            self.main_window = self.app.window(title=self.title)
        elif sys.platform == 'darwin':
            self.app = ApplicationControl(self.app_path)
            self.app.application_process_name = self.title
        else:
            raise Exception('Method not implemented for this OS')
        self.elements = self.find_objects()

    def click_on_text(self, text: str):
        cord = self.get_object_position_by_text(text)
        self.focus_on_window()
        pyautogui.FAILSAFE = False
        pyautogui.click(cord[0] + 5, cord[1] + 5)

    def find_objects(self, text='', control_type=''):
        """Returns an iterable containing the matching object

        :param text:
        :param control_type:
        :return:
        """
        if sys.platform == 'win32':
            elements = []
            if not text:
                elements = self.main_window.descendants()
            for element in self.main_window.descendants():
                if text == element.element_info.name:
                    elements.append(element)
                elif re.search(rf'.*{text}.*', element.element_info.automation_id):
                    elements.append(element)
            if control_type:
                return [i for i in elements if i.element_info.control_type.lower() == control_type.lower()]
            return elements

        elif sys.platform == 'darwin':
            raise Exception('Method not implemented for this OS')
        else:
            raise Exception('Method not implemented for this OS')

    def get_object_details(self, text='', control_type=''):
        elements = []
        for element in self.find_objects(text, control_type):
            element_info_dict = {}
            for element_info in dir(element.element_info):
                if not element_info.startswith('_'):
                    element_info_dict = element.element_info.dump_window()
            elements.append(element_info_dict)
        return elements

    def get_object_position_by_text(self, text):
        """Return position as tuple (xl, yt, xr, yb)"""
        if sys.platform == 'win32':
            pos = self.get_object_details(text)[0]['rectangle']
            return pos.left, pos.top, pos.right, pos.bottom
        elif sys.platform == 'darwin':
            return self.app.get_text_position(text)
        else:
            raise Exception('Method not implemented for this OS')

    def focus_on_window(self):
        if sys.platform == 'win32':
            self.main_window.set_focus()
        elif sys.platform == 'darwin':
            script = f"""
                tell application "System Events"
                    tell (application process "{self.title}")
                        set frontmost to true
                    end tell
                end tell
                """
            run_apple_script(script)
        else:
            raise Exception('Method not implemented for this OS')
