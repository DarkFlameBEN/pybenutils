import os
import subprocess
import multiprocess
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


def get_network_services():
    """Displays the network services in the order they are contacted for a connection, along with the
    corresponding port and device for each. An asterisk (*) next to a service means the service is inactive.

    :return: list of dicts
    :rtype: list
    """
    cmd = 'networksetup -listnetworkserviceorder'
    result_list = []
    info_dict = {}
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    for line in iter(result.stdout.readline, "".encode()):
        decoded_line = line.decode()
        if decoded_line.split() and decoded_line.split()[0][0].startswith('('):
            if decoded_line.split()[0][1].isdigit():
                info_dict['index'] = decoded_line.split()[0][1]
                info_dict['name'] = decoded_line[3:].strip()
            else:
                hardware = 'Hardware Port: '
                hardware_index = decoded_line.index(hardware)
                device = 'Device: '
                device_index = decoded_line.index(device)
                info_dict['hardware_port'] = decoded_line[hardware_index + len(hardware):device_index - 2]
                info_dict['device'] = decoded_line.strip()[device_index + len(device):-1]
                result_list.append(dict(info_dict))
    return result_list


def get_bundle_id_by_name(app_name):
    """Returns the apple bundle id of an application by its name
    :param app_name: Application name
    :return: Bundle id or None
    """
    cmd = '''id of app "{name}"'''.format(name=app_name)
    logger.debug(cmd)
    return run_apple_script(cmd)


def create_folder_as_admin(folder_path, admin_password):
    """Creates a new folder with terminal command as admin

    :param folder_path: Full folder path
    :param admin_password: The admin user password
    :return: True if successful (or already exists)
    """
    if not os.path.isdir(folder_path):
        cmd = 'echo {pwd} | sudo -S mkdir "{name}"'.format(pwd=admin_password, name=folder_path)
        p = subprocess.Popen([cmd], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
        stdout, stderr = p.communicate()
        if stderr and stderr != 'Password:':
            logger.error(stderr)
            return False
    return True


def kill_java_process(admin_password):
    logger.debug('Killing "java" process')
    cmd = 'echo {sudo_pass} | sudo -S killall java'.format(sudo_pass=admin_password)
    subprocess.Popen([cmd],
                     shell=True,
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)


def restore_default_proxy_settings(ethernet_name='Ethernet', admin_password='1234'):
    """Restoring system proxy settings to "off" and killing the "java" process

    :param ethernet_name: The ethernet device name
    :param admin_password: Local user admin password
    """
    logger.debug('Changing network proxy state to off by cmd')
    cmd = 'echo {sudo_pass} | sudo -S networksetup -setwebproxystate {adaptor} off ; ' \
          'echo {sudo_pass2} | sudo -S networksetup -setsecurewebproxystate {adaptor2} off'.format(
           sudo_pass=admin_password, adaptor=ethernet_name, sudo_pass2=admin_password, adaptor2=ethernet_name)
    subprocess.Popen([cmd],
                     shell=True,
                     stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)


def run_apple_script(cmd, timeout=300):
    """
    run apple script and return result. the script will run in a different process so if python crashes we will not
    fail. if the apple script doesn't return answer within the timeout, it will be terminated
    :param cmd: apple script
    :param timeout: timeout to end the apple script process
    :return: apple script result if exist
    """

    def _run_apple_script_in_another_process(cmd, stdout_queue, stderr_queue):
        apple_script_process = subprocess.Popen(['osascript'], shell=True, stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p_stdout, p_stderr = apple_script_process.communicate(cmd)
        if p_stdout:
            stdout_queue.put(p_stdout)
        if p_stderr:
            stderr_queue.put(p_stderr)

    # logger.debug('Going to run the apple script: {}'.format(cmd))
    stdout_queue_obj = multiprocess.Queue()
    stderr_queue_obj = multiprocess.Queue()
    p = multiprocess.Process(target=_run_apple_script_in_another_process, args=(cmd, stdout_queue_obj,
                                                                                stderr_queue_obj))
    p.start()
    p.join(timeout=timeout)
    if p.is_alive():
        logger.error('The process that runs the apple script was terminated after reaching the timeout')
        p.terminate()
    if not stderr_queue_obj.empty():  # if stderr, log the error and return None
        logger.error(stderr_queue_obj.get())
        return
    if not stdout_queue_obj.empty():
        stdout = stdout_queue_obj.get()
        # logger.debug('Apple script result is: {}'.format(stdout))
        return stdout
