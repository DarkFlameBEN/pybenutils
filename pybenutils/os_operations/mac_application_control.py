import os
import re
import sys
import time
from pybenutils.utils_logger.config_logger import get_logger

if sys.platform != 'win32':
    from pybenutils.os_operations.mac_operations import get_bundle_id_by_name, run_apple_script

logger = get_logger()


class AppElement:
    def __init__(self, element_type, element_value, element_path):
        self.type = element_type
        self.value = element_value
        self.path = element_path

    @property
    def type(self):
        return self.__type

    @type.setter
    def type(self, element_type):
        self.__type = element_type

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, element_value):
        self.__value = element_value

    @property
    def path(self):
        return self.__path

    @path.setter
    def path(self, element_path):
        self.__path = element_path

    def __dict__(self):
        return {"type": self.type, "value": self.value, "path": self.path}

    def __str__(self):
        return str(self.__dict__)


class ApplicationControl:
    def __init__(self, application_file_path, system_level_application='System Events'):
        self.application_path = application_file_path
        self.app_name = os.path.basename(application_file_path).split('.app')[0]
        self.application_process_name = None  # dynamically inserted in the launch method
        self.bundle_id = None
        self.system_level_application_name = system_level_application
        self.elements_in_current_view = []

    def get_application_process_name(self):
        if not self.application_process_name:
            get_application_process_name_script = \
                'tell application "{sys_app}" \n set application_id to (get the id of application "{app_name}" as ' \
                'string) \n set process_name to name of (application processes where bundle identifier is ' \
                'application_id) \n end tell'.format(sys_app=self.system_level_application_name, app_name=self.app_name)
            name = run_apple_script(get_application_process_name_script).strip()
            if name:
                logger.debug('Application process name is: {}'.format(name))
                self.application_process_name = name
        return self.application_process_name

    def launch(self, arguments=None, timeout=60):
        """Launches the Installer with the specified path.
        :param arguments: Execution arguments
        :param timeout: Seconds to wait for the installer to initiate
        :return: True if the installer window is detected and has content
        """
        # Adding the args to the cmd
        if arguments and type(arguments) in [str, bytes]:
            arguments = [arguments]

        args_str = ' --args {params}'.format(params=' '.join(arguments)) if arguments else ''
        cmd = 'open "{file_path}"{params}'.format(file_path=self.application_path, params=args_str)
        if not os.path.exists(self.application_path):
            logger.error('No file was found at {fp}'.format(fp=self.application_path))
            return False
        error_code = os.system(cmd)
        if int(error_code) != 0:
            logger.error('The installer\'s launch command failed with error code {}'.format(error_code))
            return False
        final_timeout = time.time() + timeout
        while time.time() < final_timeout:
            if not self.application_process_name:
                self.application_process_name = self.get_application_process_name()
            else:
                if self.is_running() and self.is_window_content_accessible():
                    break
            time.sleep(5)
        else:
            logger.error('Application was not launched')
            return False
        return True

    def is_elements_exists(self, use_cache=True, *expected_values):
        """Verifies all the expected Values/Titles strings exists in the application

        :param expected_values: Values and titles to search for
        :param use_cache: the check will be done using the known elements from previous check of the view. if the cache
        is empty, a new check of the view will be done
        :return: True if all are found
        """
        logger.debug('Checking if the following elements exist: {}'.format(expected_values))
        if use_cache and self.elements_in_current_view:
            logger.debug('Checking in the cached elements')
            elements_in_view = self.elements_in_current_view
        else:
            logger.debug('Checking in the view elements')
            elements_in_view = self.get_elements_in_view()
            if not elements_in_view:  # handle a scenario where the self.get_elements_in_view() method fail
                logger.error('Failed to get view elements. Retrying')
                elements_in_view = self.get_elements_in_view()
            if not elements_in_view:
                logger.error('Failed to get view elements. Aborting the check')
                return

        existing_values_list = list(set([element_value.value for element_value in elements_in_view if element_value]))
        for expected_value in list(set(expected_values)):
            expected_value = expected_value
            logger.debug('Checking if the following element exist: {}'.format(expected_value))
            for existing_element_str_value in existing_values_list:
                if existing_element_str_value == str(expected_value):
                    break
            else:
                return False
        return True

    def get_elements_in_view(self):
        """Returns a list of detected elements within the application current view

        :return: List of objects [{"type": 'the element role, "value": 'value or title', "path": 'position path'}]
        """
        logger.debug('Getting all elements in the view of "{}"'.format(self.get_application_process_name()))
        window_objects_dict_list = []

        # get all elements paths
        get_elements_apple_script = \
            'tell application "{sys_app}" to tell front window of application process "{app_name}" to return entire ' \
            'contents'.format(sys_app=self.system_level_application_name, app_name=self.get_application_process_name())
        result = run_apple_script(get_elements_apple_script)
        if not result:
            logger.error('Failed to get elements when running {}'.format(get_elements_apple_script))
            return
        application_process_name = re.findall('application process (.+?),', result)[0]
        elements_list = re.findall('(.+? application process {}), '.format(application_process_name), result)
        paths_list = [item[item.index('of'):] for item in elements_list]
        if not paths_list:
            logger.error('Failed to get elements\' paths')
            return
        application_process_name = re.findall('application process (.+)', paths_list[0])[0]
        for index, path in enumerate(paths_list):  # wrap the main application process name with ""
            paths_list[index] = path.replace(application_process_name, '"{}"'.format(application_process_name))

        # get all elements names and classes
        get_elements_details_apple_script = \
            'set final to {{}}\n tell application "{sys_app}" \n tell front window of application process ' \
            '"{app_name}" \n repeat with ui_element in entire contents as list \n set current_ui to name of ' \
            'ui_element as string & ";" & class of ui_element as string & "$"\n set final to final & current_ui \n ' \
            'end repeat \n return final \n end tell \n end tell'.format(sys_app=self.system_level_application_name,
                                                                        app_name=self.get_application_process_name())
        result = run_apple_script(get_elements_details_apple_script)
        if not result:
            logger.error('Failed to get elements when running {}'.format(get_elements_details_apple_script))
            return
        elements_details_list = re.findall(r'(.+?)\$, ', result)
        elements_details_dict_list = [{'value': item.split(';')[0].strip(), 'class': item.split(';')[1]} for item in
                                      elements_details_list]
        if not elements_details_dict_list:
            logger.error('Failed to get elements\' details')
            return
        if len(paths_list) != len(elements_details_dict_list):
            logger.error('There\'s a Mismatch between the number of element\'s paths ({num_p}) and the number of '
                         'elements details ({num_d})'.format(num_p=len(paths_list),
                                                             num_d=len(elements_details_dict_list)))
            return

        # initiate an AppElement instance with the element's class, value and path
        for index, element_details in enumerate(elements_details_dict_list):
            element_class = element_details['class']
            try:
                element_value = str(element_details['value'])
            except UnicodeEncodeError:
                element_value = str(element_details['value'].encode('utf8'))
            element_value = element_value if element_value != 'missing value' else ''

            element_path = paths_list[index]
            #  wrap the parent window with "" if it exists and if it's not an integer
            reg_obj = re.findall('of window (.+?) of', element_path)
            parent_window = reg_obj[0] if reg_obj else ''
            if parent_window and not parent_window.isdigit():
                element_path = element_path.replace(parent_window, '"{}"'.format(parent_window))

            window_objects_dict_list.append(AppElement(element_type=element_class,
                                                       element_value=element_value,
                                                       element_path=element_path))
        self.elements_in_current_view = window_objects_dict_list
        return self.elements_in_current_view

    def wait_for_element(self, title, timeout=60, use_cache=True):
        """Wait for an element with the given title to be on view

        :param title: Title of the searched element
        :param timeout: Timeout in seconds for the operation
        :param use_cache: If True, will first search in the data from latest view update
        :return: The requested element if found
        """
        try:
            title = str(title)
        except UnicodeEncodeError:
            title = str(title.encode('utf-8'))
        logger.debug('Waiting for an element with the title "{}"'.format(title))
        if use_cache:
            known_elements_with_value = [element for element in self.elements_in_current_view if element.value]
            for obj in known_elements_with_value:
                if obj.value == title:
                    return obj
            logger.debug('Failed to get the element from the cache, trying to refresh the element list')
        cmd = ''
        seconds_wait_before_retry = int(timeout / 10) if int(timeout / 10) > 0 else 1
        final_timeout = time.time() + timeout
        while not cmd and time.time() < final_timeout:
            found_elements = self.get_elements_in_view()
            if found_elements:
                found_elements_with_value = [element for element in found_elements if element.value]
                for obj in found_elements_with_value:
                    if obj.value == title:
                        return obj
            time.sleep(seconds_wait_before_retry)
        if not cmd:
            return None

    def set_element_value(self, element_role, element_position_path, new_value):
        """Set value of element_role of element_position_path to new_value

        :param element_role: The element role like "button"
        :param element_position_path: The element position inside the application view
        :param new_value: The new requested value
        :return: True if successful
        """
        cmd = '''on run {}
                tell application "''' + self.system_level_application_name + '''"
                tell application process "''' + self.get_application_process_name() + '''"
                set value of ''' + element_role + ''' of ''' + element_position_path + ''' to "''' + new_value + '''"
                end tell
                end tell
                end run'''
        result = run_apple_script(cmd)
        return bool(result)

    def get_bundle_id(self):
        """Returns the application bundle id"""
        if self.bundle_id:
            return self.bundle_id
        self.bundle_id = get_bundle_id_by_name(self.app_name)
        logger.debug(self.bundle_id)
        return self.bundle_id

    def get_text_position(self, text):
        """Return the position of a text in the application (upper left corner)
        :param text: Text to locate
        :return: (pos_x, pos_y)
        """
        obj = self.wait_for_element(title=text)
        if not obj:
            return False
        cmd = 'tell application "{sys_app_name}" to return position of {xtype} "{xvalue}" {xpath}'.format(
            sys_app_name=self.system_level_application_name,
            xtype=obj.type,
            xvalue=obj.value,
            xpath=obj.path)
        time.sleep(1)
        result = run_apple_script(cmd)
        if not result:
            return False
        pos_x = int(result.split(",")[0].strip())
        pos_y = int(result.split(",")[-1].split("\n")[0].strip())
        return pos_x, pos_y

    def click_by_title(self, title, timeout=60, use_cache=True):
        """Clicks on an object by its title / text / name. Trying twice as default.

        :param title: Title / text / name
        :param timeout: Timeout in seconds for object to appear
        :param use_cache: Try first on the last known location of the requested element
        :return: True if success
        """
        start_time = time.time()
        estimated_end_time = start_time + timeout
        obj = self.wait_for_element(title=title, timeout=timeout, use_cache=True)
        if not obj:
            return False
        cmd = 'tell application "{sys_app_name}" to click {xtype} "{xvalue}" {xpath}'.format(
            sys_app_name=self.system_level_application_name,
            xtype=obj.type,
            xvalue=obj.value,
            xpath=obj.path)
        time.sleep(1)
        logger.debug('Trying to click on {cmd}'.format(cmd=cmd))
        result = run_apple_script(cmd)
        if not result:
            if use_cache:
                # We want to try again without cache:
                # 1. Its possible that because of cache we are trying to press a ghost element
                # 2. We want to try again to eliminate mac voodoo (Didn't load, Didn't respond, etc..)
                return self.click_by_title(title=title, timeout=int(estimated_end_time - time.time()), use_cache=False)
            else:
                return False
        return True

    def close(self):
        """Closes the installer gracefully"""
        terminal_command = 'osascript -e \'quit app "' + self.application_path + '"\''
        os.system(terminal_command)

    def kill(self):
        """Kills the app"""
        process_name = self.get_application_process_name()
        os.system(f'pkill {process_name}')
        time.sleep(1)

    def get_app_name(self):
        """Returns the app name"""
        return self.app_name

    def is_running(self):
        """Returns True if the application is running"""
        app_name = self.application_process_name if self.get_application_process_name() else self.app_name
        cmd = 'tell application "{sys_app_name}" to (name of processes) contains "{app_name}"'.format(
            sys_app_name=self.system_level_application_name, app_name=app_name)
        time.sleep(1)
        result = run_apple_script(cmd).strip()
        return result == 'true'

    def is_window_content_accessible(self):
        """Checks if the application is alive its window content is accessible"""
        get_elements_apple_script = \
            'tell application "{sys_app}" to tell front window of application process "{app_name}" to return entire ' \
            'contents'.format(sys_app=self.system_level_application_name, app_name=self.get_application_process_name())
        objects_list = run_apple_script(get_elements_apple_script)
        return bool(objects_list)

    def get_window_position(self):
        """Returns a tuple with the window (x,y) position"""
        cmd = 'tell application "{sys_app_name}" to return position of window 1 of application process' \
              ' "{app_name}"'.format(sys_app_name=self.system_level_application_name,
                                     app_name=self.get_application_process_name())
        result = run_apple_script(cmd)
        if result:
            pos_x = result.split(",")[0].strip()
            pos_y = result.split(",")[-1].split("\n")[0].strip()
            return pos_x, pos_y

    def get_short_version(self):
        """Returns the CFBundleShortVersionString from the package info.plist

        :return: Application version or an empty sting if not found
        """
        version = ''
        plist_file_path = '{app}/Contents/Info.plist'.format(app=self.application_path)
        if os.path.exists(plist_file_path):
            with open(plist_file_path, 'r') as plist_file:
                lines = plist_file.read()
            re_match = re.search(r'.*<key>CFBundleShortVersionString</key>\n\s<string>(.*)</string>', lines)
            if re_match:
                version = re_match.group(1)
        return version

    def get_bundle_id_from_package(self):
        """Returns the CFBundleIdentifier from the package info.plist

        :return: Application bundle id or an empty sting if not found
        """
        version = ''
        plist_file_path = '{app}/Contents/Info.plist'.format(app=self.application_path)
        if os.path.exists(plist_file_path):
            with open(plist_file_path, 'r') as plist_file:
                lines = plist_file.read()
            re_match = re.search(r'.*<key>CFBundleIdentifier</key>\n\s<string>(.*)</string>', lines)
            if re_match:
                version = re_match.group(1)
        return version
