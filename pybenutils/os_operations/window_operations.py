import sys
from typing import List, Union
from pybenutils.utils_logger.config_logger import get_logger
if sys.platform == 'win32':
    import win32gui
    import win32api
    import win32process
    import win32con

logger = get_logger()


def is_process_running_by_path(file_path: str):
    """Check if process running by its exe path
    >>> is_process_running_by_path('C:\\Windows\\explorer.exe')
    True
    :param file_path: file path
    """
    processes = win32process.EnumProcesses()
    for pid in processes:
        try:
            handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
            exe = win32process.GetModuleFileNameEx(handle, 0)
            if exe.lower() == file_path.lower():
                return True
        except:
            pass
    return False


def close_window_by_hwnd(hwnd: int):
    """Close window by window handle (HWND)

    :param hwnd: HWND in decimal
    """
    if window_exist_by_hwnd(hwnd):
        try:
            set_focus_on_window(hwnd)
        except Exception:
            logger.debug('Could not set focus on window. continue...')
        try:
            flags = win32con.SMTO_BLOCK + win32con.SMTO_ABORTIFHUNG + win32con.SMTO_NOTIMEOUTIFNOTHUNG
            win32gui.SendMessageTimeout(hwnd, 0x10, 0, 0, flags, 1000)
            win32gui.SendMessageTimeout(hwnd, 0x10, 0, 0, flags, 1000)
        except Exception as e:
            logger.debug('Got error while trying to close the window, details:{error}'.format(error=e))
        return True
    else:
        logger.debug('Could not find the HWND: {}'.format(hwnd))
        return False


def get_window_text(hwnd: int) -> str:
    """Get window text (title) by window handle (HWND).

    :param hwnd: HWND in decimal
    """
    return win32gui.GetWindowText(hwnd)


def find_window(window_class: str = None, window_title: str = None):
    """Get window handle (HWND) by class or/and title.

    :param window_class: Window class name
    :param window_title: Window title name
    :return: Window handle (HWND)
    """
    hwnd = win32gui.FindWindowEx(0, 0, window_class, window_title)
    if window_exist_by_hwnd(hwnd):
        return hwnd
    else:
        logger.debug('Could not find the window with class "{w_class}" and title "{w_title}"'.format(
            w_class=window_class, w_title=window_title))
        return False


def get_process_id_by_hwnd(hwnd: int):
    """Get process id by window handle (HWND).

    :param hwnd: Window handle (HWND)
    :return: HWND process ID
    """
    if window_exist_by_hwnd(hwnd):
        return win32gui.GetDlgCtrlID(hwnd)
    else:
        logger.debug('Could not find the HWND: {}'.format(hwnd))
        return False


def get_hwnd_by_class(window_class: str) -> int:
    """Get window handle (HWND) by class. Will return the last top-level window from the class.

    :param window_class: Window class name
    :return: Window handle (HWND)
    """
    def callback(hwnd, inputs):
        try:
            if inputs['equals'] == win32gui.GetClassName(hwnd):
                inputs['res'] = hwnd
        except:  # Skipping protected, unavailable & unresponsive window handles
            pass

    extra = {'res': None, 'equals': window_class}
    win32gui.EnumWindows(callback, extra)
    return extra['res']


def get_hwnds_by_class(window_class: str) -> List[int]:
    """Returns a list of  window handles (HWND) by class

    :param window_class: Window class name
    :return: List of window handles (HWND)
    :rtype: list
    """
    def callback(hwnd, inputs):
        if inputs['equals'] == win32gui.GetClassName(hwnd):
            inputs['res'].append(hwnd)

    extra = {'res': [], 'equals': window_class}
    win32gui.EnumWindows(callback, extra)
    return extra['res']


def get_child_hwnd_by_class(hwnd: int, window_class: str) -> int:
    """Enumerates the child windows that belong to the specified parent window by passing the handle to
     each child window.

    :param hwnd: HWND in decimal
    :param window_class: window class name
    :return: window handle (HWND)
    """
    def callback(hwnd, extra):
        if extra['equals'] == win32gui.GetClassName(hwnd):
            extra['res'] = hwnd

    extra = {'res': None, 'equals': window_class}
    win32gui.EnumChildWindows(hwnd, callback, extra)
    return extra['res']


def download_folder_focus():
    """ Set focus on download folder

    """
    hwnd = win32gui.FindWindow("CabinetWClass", "Downloads")
    if hwnd != 0 and hwnd is not None:
        try:
            set_focus_on_window(hwnd)
        except Exception as e:
            logger.debug('could not set focus on window. continue...')
        click_on_point(hwnd, 1, 1)
        return hwnd
    else:
        logger.debug('Could not find Download folder window')
        return False


def close_download_folder():
    """Close download folder"""
    hwnd = win32gui.FindWindow("CabinetWClass", "Downloads")
    if hwnd != 0 and hwnd is not None:
        win32api.SendMessage(hwnd, 0x10, 0, 0)
        return hwnd
    else:
        logger.debug('Could not find Download folder window')
        return False


def set_focus_on_window(hwnd):
    """Bring a window to the foreground

    :param hwnd: hwnd of window
    """
    if window_exist_by_hwnd(hwnd):
        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetActiveWindow(hwnd)
        return True
    else:
        logger.debug('Could not find the HWND: {}'.format(hwnd))
        return False


def window_exist(window_class, window_title):
    """Return bool if window exist by its class and title

    :param window_class: window class
    :param window_title: window title
    :return: True/False
    :type window_class: str
    :type window_title: str
    :rtype: bool
    """
    hwnd = win32gui.FindWindow(window_class, window_title)
    return True if hwnd != 0 and hwnd is not None else False


def window_exist_by_hwnd(hwnd: int) -> bool:
    """ Return bool if window exist by its HWND

    :param hwnd: HWND in decimal
    :return: True/False
    :rtype: bool
    """
    result = win32gui.IsWindowVisible(hwnd)
    return True if result != 0 else False


def get_hwnds_by_pid(pid: Union[int, str], only_enabled_visible_windows=False):
    """Get all the window handles (HWND) associated with the given pid

    :param pid: Process ID
    :param only_enabled_visible_windows: Return only hwnd which are visible and enabled
    :return: List of window handles (HWND)
    """
    def callback(hwnd, parameters_dict):
        try:
            thread_id, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if parameters_dict['pid'] == process_id:
                if not only_enabled_visible_windows:
                    parameters_dict['hwnd_list'].append(hwnd)
                elif win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                    parameters_dict['hwnd_list'].append(hwnd)
        except:  # Skipping protected, unavailable & unresponsive window handles
            pass

    extra = {'hwnd_list': [], 'pid': int(pid)}
    win32gui.EnumWindows(callback, extra)
    return extra['hwnd_list']


def get_hwnd_details(hwnd: Union[int, str]):
    """Returns a dict with details about the given hwnd (From the win32gui lib)

    Details:
      -  hwnd
      -  GetWindowText
      -  GetWindowRect
      -  IsWindowVisible - Windows can be hidden behind other windows
      -  IsWindowEnabled
      -  IsWindow

    :param hwnd: A Windows window handle number
    :return: Dict with details about the given hwnd.
     Errors will be logged. Failing functions will return with None value
    """
    def callback(hwnd, parameters_dict):
        functions = [win32gui.GetWindowText, win32gui.GetWindowRect, win32gui.IsWindowVisible,
                     win32gui.IsWindowEnabled, win32gui.IsWindow]
        if int(hwnd) == int(parameters_dict['hwnd']):
            for func in functions:
                func_name = func.__name__
                try:
                    parameters_dict[func_name] = func(hwnd)
                except Exception as ex:
                    # Since the handle was being requested by the user, its appropriate to display errors
                    logger.error(f'Failed to execute "{func_name}({hwnd})" for error: {ex}')
                    parameters_dict[func_name] = None

    results_dict = {'hwnd': hwnd}
    win32gui.EnumWindows(callback, results_dict)
    return results_dict


def get_visible_enabled_windows_details(pid: Union[int, str]):
    """Returns a list of dicts with details of enabled visible windows. Windows can be hidden behind other windows

    Details:
      -  hwnd
      -  GetWindowText
      -  GetWindowRect
      -  IsWindowVisible - Will always be 1
      -  IsWindowEnabled - Will always be 1
      -  IsWindow

    :param pid: A Windows process id
    :return: list of dicts with details of visible windows
    """
    return [get_hwnd_details(hwnd) for hwnd in get_hwnds_by_pid(pid, only_enabled_visible_windows=True)]


def click_on_point(hwnd, x, y):
    """Click on point inside a window

    :param hwnd: window hwnd
    :param x: x position
    :param y: y position
    """
    set_focus_on_window(hwnd)
    old_pos = win32gui.GetCursorPos()
    # Get window x,y position
    rect = win32gui.GetWindowRect(hwnd)
    win32api.SetCursorPos((rect[0] + x + 2, rect[1] + y + 2))
    win32api.mouse_event(0x00000002, 0, 0, 0, 0)  # left mouse button up
    win32api.mouse_event(0x00000004, 0, 0, 0, 0)  # left mouse button up
    # Set to old position
    win32api.SetCursorPos(old_pos)


def mouse_click(x: int, y: int):
    """Click on screen by x & y position

    :param x: X position
    :param y: Y position
    """
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)


def get_cursor_position():
    """Get mouse cursor (x, y) position"""
    return win32api.GetCursorPos()
