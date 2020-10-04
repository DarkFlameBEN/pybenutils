import os
import time
import psutil
from psutil import AccessDenied
from psutil import process_iter
from pybenutils.utils_logger.config_logger import get_logger
from typing import Callable, Any, List

logger = get_logger()


class ProcessHandler(object):
    def __init__(self, process_name):
        self.proc_list = self.get_processes_by_name(process_name)
        self.process_name = process_name

    @staticmethod
    def get_processes_by_name(process_name: str) -> List:
        """Return processes object list

        :param process_name: Process name
        :return: Process object list
        """
        processes_list = []
        process_name = os.path.basename(process_name)
        for p in process_iter():
            try:
                name = p.name()
                if name.lower() == process_name.lower():
                    processes_list.append(p)
            except (AccessDenied, psutil.NoSuchProcess):
                pass
        return processes_list

    def get_processes_child_process_name_list(self):
        """Get children processes"""
        processes = []
        process_name = os.path.basename(self.process_name)

        excluded_list = ["searindexer", "java", "services", "winlogon", "csrss", "smss", "audiodg", "System", "sppsvc",
                         "dllhost", "conhost", "SearchFilterHost", "SearchProtocolHost", "svchost"]

        for p in psutil.process_iter():
            try:
                if process_name.lower() == p.parent().name().lower():
                    name = p.name()
                    if not any(True for w in excluded_list if w in name):
                        processes.append(name)
            except Exception:
                pass
        logger.debug(', '.join(processes))
        return processes

    def close_process(self):
        """Free all associated of this process"""
        for proc in self.proc_list:
            proc.kill()

    def kill_process(self):
        """Immediately stop the associated process"""
        for proc in self.proc_list:
            proc.kill()

    def process_exists(self) -> bool:
        """Return True if process exist

        :return: If process exists
        """
        if self.proc_list:
            return True
        else:
            return False

    @staticmethod
    def get_loaded_dll_list_in_file(process_obj=None, pid=None, process_name=None):
        """Returns a list of dll loaded in the process. Input can be given for the inspected process in 3 ways:
        process name, pid and process object (psutil.Process instance). Only one will be used, according to the order
        in the method's signature

        :param process_obj: Psutil.Process instance of the process to inspect
        :param pid: Pid of the process to inspect
        :param process_name: Process name to inspect, if no processes are running with the given name, an assertion
        error will be raised and if more than one is running, the first found will be used
        :return: List of dll names that were loaded in the process
        """
        assert bool(process_obj) | bool(pid) | bool(process_name), 'Dll inspection aborted, no input was given'
        if not process_obj and not pid:
            process_list = ProcessHandler.get_processes_by_name(process_name)
            assert process_list, f'Dll inspection aborted, no running processes were for "{process_name}"'
            process_obj = process_list[0]
        if not process_obj:
            process_obj = psutil.Process(pid)
        dll_list = sorted([os.path.basename(dll.path.lower()) for dll in process_obj.memory_maps()])
        logger.debug('The installer loaded the following dlls: {}'.format(dll_list))
        return dll_list


def wait_for_process_to_close(process_name: str, timeout=10):
    """Returns True if a process closed within the given timeout

    :param process_name: Process name
    :param timeout: Timeout in seconds
    :return: True if a process closed within the given timeout
    """
    end_time = time.time() + int(timeout) * 60
    while time.time() < end_time:
        if not ProcessHandler(process_name).process_exists():
            logger.debug(f"The process: {process_name} was closed")
            return True
        time.sleep(1)
    else:
        logger.error(f"Time-out accorded before the process: {process_name} was closed")
        return False


def kill_process(process_obj):
    """Kill a given process and return result

    :param process_obj: Psutil.process object
    :return: True if the process was killed
    """
    process_killed = False
    try:
        process_obj.kill()
        check_time = 5
        timeout = time.time() + check_time
        while time.time() < timeout:
            if not process_obj.is_running():
                process_killed = True
                logger.debug('The process was killed')
                break
            time.sleep(1)
        else:
            logger.error(f'The kill command was sent for the process but it\'s still alive after {check_time} '
                         f'seconds')
    # ignore race-condition cases when the process was found but terminated before the function killed it
    except psutil.NoSuchProcess:
        logger.debug('The process was terminated by another thread')
        process_killed = True
    return process_killed


def process_should_not_be_running(process_name, error=True):
    """Check if a process is still running

    :param process_name: process name or path
    :param error: raise error (True) or return result (False)
    :type error: bool
    :return: if "error" is set to "False" will return process result
    """
    exists = ProcessHandler(os.path.basename(process_name)).process_exists()
    if not exists:
        logger.info('process {} is not running'.format(os.path.basename(process_name)))
        return True

    message = 'process {} is still running'.format(os.path.basename(process_name))
    if error:
        raise AssertionError(message)

    logger.error(message)
    return False


def process_should_be_running(process_name, error=True):
    """Check if a process is not running

    :param process_name: process name or path
    :param error: raise error (True) or return result (False)
    :type error: bool
    :return: if "error" is set to "False" will return process result
    """
    exists = ProcessHandler(os.path.basename(process_name)).process_exists()
    if exists:
        logger.info('process {} is still running'.format(os.path.basename(process_name)))
        return True

    message = 'process {} is not running'.format(os.path.basename(process_name))
    if error:
        raise AssertionError(message)

    logger.error(message)
    return False


def kill_process_by(condition: Callable[[Any], bool], kill_children=False, kill_all_instances=False):
    """Kill process by boolean condition

    :param condition: Any boolean condition for the process to kill (Using lambda is advised)
    :param kill_children: True/False
    :param kill_children: Kill child processes along with the main one
    :param kill_all_instances: Don't finish after the first found process was killed
    :returns True if any processes were killed
    """
    process_killed = False
    found = 0
    killed = 0
    for p in psutil.process_iter():
        try:
            condition_result = condition(p)
        except Exception as ex:
            logger.error(ex)
            continue

        if condition_result:
            found += 1
            if kill_children:
                logger.debug('Kill child processes')
                for child in p.children(recursive=True):
                    kill_process(child)
                logger.debug('All child processes were killed')
            if kill_process(p):
                killed += 1
            if not kill_all_instances:
                break
    if found == 0:
        logger.debug(f'No process was found matching the input condition')
    else:
        logger.debug(f'{"A process was" if found == 1 else f"{found} process were"} found matching the input condition')
        if found != killed:
            logger.error(f'{" Only" if killed != 0 else ""} {killed} of the processes '
                         f'{"was" if killed in [1 ,0] else "were"} killed successfully')
        else:
            logger.debug(f'{"The process was" if killed == 1 else "All found process were"} killed successfully')
            process_killed = True
    return process_killed


def kill_process_by_cmd(partial_cmd_line: str, kill_children=False, kill_all_instances=False):
    """Kills all processes which cmdline attribute contains the given input

    :param partial_cmd_line: Text to be searched in the running processes cmdline attribute
    :param kill_children: Kill child processes along with the main one
    :param kill_all_instances: Don't finish after the first found process was killed
    :return True if all processes killed successfully
    """
    logger.debug(f'Looking for a process who\'s cmd line contains "{partial_cmd_line}" to kill')
    return kill_process_by(condition=lambda p: partial_cmd_line in ' '.join(p.cmdline()),
                           kill_children=kill_children,
                           kill_all_instances=kill_all_instances)


def kill_process_by_name(process_name: str, kill_children=False, kill_all_instances=False, add_ext_to_file=True):
    """Kill process by name

    :param add_ext_to_file: Add or don't add ".exe" to the tested file process name.
    :param process_name: Name of the process to kill
    :param kill_children: Kill child processes along with the main one
    :param kill_all_instances: Don't finish after the first found process was killed
    :return True if all processes killed successfully
    """
    process_name = os.path.basename(process_name)
    if add_ext_to_file and ".exe" not in process_name and "." not in process_name:
        process_name = process_name + ".exe"
    process_name_to_find = process_name.lower()
    logger.debug(f'Looking for a process with the name "{process_name_to_find}" to kill')
    return kill_process_by(condition=lambda p: p.name().lower() == process_name_to_find,
                           kill_children=kill_children,
                           kill_all_instances=kill_all_instances)


def kill_process_by_pid(pid: int, kill_children=False):
    """Kill process by pid

    :param pid: the pid to kill
    :param kill_children: Kill child processes along with the main one
    :return True if all processes killed successfully
    """
    logger.debug(f'Looking for a process with the pid "{pid}" to kill')
    return kill_process_by(condition=lambda p: p.pid == pid,
                           kill_children=kill_children)


def get_all_running_processes(attrs_filter=('pid', 'name')):
    """The function returns information on all currently running processes

    :param attrs_filter: List of attribute that will be returned for each process. Pass empty to get all attributes.
        Example attributes: 'name', 'pid', 'ppid', 'cmdline', 'cpu_num', 'open_files', 'threads', 'uids', 'username'.
        For a list of all available attributes see: https://psutil.readthedocs.io/en/latest/#psutil.Process.as_dict
    :return: List of Dictionaries, each representing the requested attributes of the running process
    """
    if not attrs_filter:
        attrs_filter = ()
    return [process.info for process in psutil.process_iter(attrs_filter)]
