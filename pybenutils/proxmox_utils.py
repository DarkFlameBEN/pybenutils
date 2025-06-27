import json
import os
import time

from proxmoxer import ProxmoxAPI

from pybenutils.cli_tools import cli_main_for_class
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


class Proxmox(ProxmoxAPI):
    def __init__(self, host='', user='', password=''):
        """ProxmoxAPI constructor

        :param host: Proxmox server host
        :param user: Proxmox server user
        :param password: Proxmox server password
        """
        self.host = host if host else os.environ.get("PROXMOX_HOST", '')
        self.user = user if user else os.environ.get("PROXMOX_USER", '')
        self.password = password if password else os.environ.get("PROXMOX_PASS", '')
        self.verify_ssl = False
        self.clone_output_file = 'new_vms.json'
        super().__init__(self.host, user=self.user,
                         password=self.password,
                         verify_ssl=self.verify_ssl)

    def pprint(self, function_name, *args, **kwargs):
        res = getattr(self, function_name)(*args, **kwargs)
        if isinstance(res, dict) or isinstance(res, list):
            return json.dumps(res, indent=4)
        else:
            return res

    def wait_for_task(self, task_obj, node, name='', vmid=0, timeout=60, interval=5):
        """Wait for a task to finish within timeout

        :param task_obj: Task object
        :param node: Node
        :param name: Vm Name
        :param vmid: Vm id
        :param timeout: Timeout in seconds
        :param interval: Interval between validations in seconds
        :return: True if task finished and succeeded, False otherwise
        """
        if not task_obj:
            return False
        task_type = ''
        task_exit_status = None
        end_time = time.time() + timeout
        status = None
        while time.time() <= end_time and not task_exit_status:
            try:
                time.sleep(interval)
                status = self.nodes(node).tasks(task_obj).status.get()
                assert status, f'Failed to get Task status for {name}:{vmid} task={task_obj}'
                task_type = status["type"]
                task_status = status['status']
                if task_status == 'stopped':
                    task_exit_status = status["exitstatus"]
            except Exception as e:
                logger.error(e)
        if task_exit_status:
            logger.info(f'Task {task_type} for {name}:{vmid} finished. Exit status is {task_exit_status}')
            return task_exit_status == 'OK'
        logger.debug(f'Task {status = }')
        logger.error(f'Task {task_type} for {name}:{vmid} did not complete within {timeout} seconds')
        return False

if __name__ == '__main__':
    cli_main_for_class(Proxmox)