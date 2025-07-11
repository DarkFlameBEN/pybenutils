import errno
import os
import subprocess
import time

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
    Run an AppleScript command using subprocess with a timeout.
    If the script exceeds the timeout, it is terminated.

    :param cmd: AppleScript as a string
    :param timeout: Timeout in seconds
    :return: Output of AppleScript if successful, None otherwise
    """
    try:
        # logger.debug('Running AppleScript: %s', cmd)
        result = subprocess.run(
            ['osascript'],
            input=cmd,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        if result.stderr:
            logger.error('AppleScript error: %s', result.stderr.strip())
            return None
        output = result.stdout.strip()
        logger.debug('AppleScript result: %s', output)
        return output if output else None
    except subprocess.TimeoutExpired:
        logger.error('AppleScript timed out after %s seconds', timeout)
        return None
    except Exception as e:
        logger.exception(e)
        return None


def mount_image_mac(image_path, raise_on_error=False, space_in_name=True):
    """Mount image in macOS

    :param image_path: Path on local storage
    :param raise_on_error: Raise Exception instead of writing error to log
    :param space_in_name: Respect spaces in volume name
    :returns Mounted volume name with removed prefix "/Volumes"
    """
    if raise_on_error and not os.path.exists(image_path):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), image_path)
    mount_name = ''
    command = f'hdiutil attach "{image_path}"'
    res = os.popen(command).read()
    if raise_on_error and not res:
        logger.error(f"{command=} failed. {res=} is empty.")
        raise Exception(os.popen(command+" 2>&1").read())
    for line in res.splitlines():
        for tab in line.split("\t") if space_in_name else line.split():
            if tab.startswith('/Volumes'):
                mount_name = tab.split('/')[-1]
                logger.debug(f"{mount_name=}")
                break
    if raise_on_error and not mount_name:
        logger.info(f"{res=}")
        raise Exception(f"{command=} failed. mount_name not found.")
    volume = os.path.join("/Volumes", mount_name)
    if raise_on_error and not os.listdir(volume):
        raise Exception(f"Mount point '{volume}' not not found.")
    return mount_name


def unmount_image_mac(mount_name, retry=1):
    """Unmount image

    :param mount_name:
    :param retry:  how much times to retry before failure.
    :returns success
    """
    dir_name = os.path.join("/Volumes", mount_name)
    command = f'hdiutil detach "{dir_name}" -verbose'
    logger.debug(f"Going to unmount {dir_name}")
    for i in range(retry):
        time.sleep(i)
        subprocess.run(command, shell=True)
        if not os.path.exists(dir_name):
            return True
        logger.error(f"Failed to unmount {dir_name}")
    return False
