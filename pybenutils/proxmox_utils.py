import json
import os
import random
import time

from proxmoxer import ProxmoxAPI
from typing import Dict, List

from pybenutils.cli_tools import cli_main_for_class
from pybenutils.network.ssh_utils import run_commands
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

        # Override this per environment to activate assert_free_hdd_space_for_cloning
        self.storage_node = ''
        self.storage_name = 'ceph-vm'

        # Override this variable to assign new cloned vms into a 'pool'
        self.new_vm_pool_name = ''
        
        # Override this for cloning vms
        self.templates = {'ben-windows11-template': {'labels': ['windows', 'windows11']}}

        super().__init__(self.host, user=self.user,
                         password=self.password,
                         verify_ssl=self.verify_ssl)

    def pprint(self, function_name, *args, **kwargs):
        res = getattr(self, function_name)(*args, **kwargs)
        if isinstance(res, dict) or isinstance(res, list):
            return json.dumps(res, indent=4)
        else:
            return res

    def wait_for_task(self, task_obj: str, node: str, task_owner='vm', timeout=60, interval=5):
        """Wait for a task to finish within timeout

        :param task_obj: Task object
        :param node: Node
        :param task_owner: The Task owner name for the log. Suggestion: '<vmid>:<Vm Name>'
        :param timeout: Timeout in seconds to wait for the task to finish
        :param interval: Interval between validations in seconds
        :return: True if the task finished and successful, False otherwise
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
                assert status, f'Failed to get Task status for {task_owner} task={task_obj}'
                task_type = status["type"]
                task_status = status['status']
                if task_status == 'stopped':
                    task_exit_status = status["exitstatus"]
            except Exception as e:
                logger.error(e)
        if task_exit_status:
            logger.info(f'Task {task_type} for {task_owner} finished. Exit status is {task_exit_status}')
            return task_exit_status == 'OK'
        logger.debug(f'Task {status = }')
        logger.error(f'Task {task_type} for {task_owner} did not complete within {timeout} seconds')
        return False

    def assert_free_hdd_space_for_cloning(self):
        """Assert that the free HDD space in the self.storage_name is above 10%"""
        node_name = self.storage_node
        storage_name = self.storage_name
        if node_name and storage_name:
            storage_info = self.nodes(node_name).storage(storage_name).status.get()
            total_space = storage_info.get("total", 1)  # Avoid division by zero
            used_space = storage_info.get("used", 0)
            usage_percent = (used_space / total_space) * 100
            print(f"Ceph-VM Storage Usage: {usage_percent:.2f}%")
            assert usage_percent < 90.0, f'Not enough free space on "{self.storage_name}"! ABORTING !!'

    def clone_vm(self, source, name='', node='', full_clone=1, failed_counter=0) -> Dict:
        """Clones a new vm from the given source

        :param source: Name of a source to clone from
        :param name: Requested vm name will be appended to the full name according to the service rules
        :param node: Request the new vm to be migrated to a specific node
        :param full_clone: 1 for full clone, 0 for linked clone
        :param failed_counter: Number of failed clone attempts
        :return: New vm dict
        """
        if not node:
            node = self.select_node_for_new_vm()
        self.assert_free_hdd_space_for_cloning()
        sources = self.select_source_by_label(source)
        if not sources:
            sources = self.get_vms_by_name(source)
        if not sources:
            raise Exception(f'Failed to find a vm / template matching the given label {source}')

        elif len(sources) > 1:
            logger.warning('There are more than one vm matching the requested name. '
                           f'The first one will be taken as a source. {sources[0]}')
        source_vm_dict = sources[0]
        new_vm_id = self.get_first_free_vm_id()
        if not name:
            name = source.split('-template')[0]

        new_vm_name = f'{name}'.replace('_', '-')
        if os.environ.get('PERMANENT_VM'):
            if new_vm_name.startswith('proxmox'):  # Code for easy Jenkins slaves identification
                new_vm_name = f'proxmox{new_vm_id}{new_vm_name.split('proxmox', 1)[-1]}'
            else:
                new_vm_name = f'{new_vm_name}{new_vm_id}'

        logger.info(f"Cloning new vm (vmid:{new_vm_id}, name:{new_vm_name}) from {source_vm_dict['name']}:"
                    f"{source_vm_dict['vmid']} at {source_vm_dict['node']}")
        arguments = {'newid': new_vm_id, 'name': new_vm_name, 'full': full_clone}
        if self.new_vm_pool_name:
            arguments['pool'] = self.new_vm_pool_name
        try:
            task_obj = self.nodes(source_vm_dict['node']).qemu(source_vm_dict['vmid']).clone.create(**arguments)
            assert self.wait_for_task(task_obj=task_obj,
                                      node=source_vm_dict['node'],
                                      task_owner=f'{new_vm_name}:{new_vm_id}',
                                      timeout=60 * 15,
                                      interval=20)
        except Exception as e:
            logger.warning(f'Failed to clone vm for exception: {e}.\nWill retry after 2 minutes')
            assert failed_counter < 10, 'Too many failed clone attempts. Aborting operation'
            time.sleep(60 * 2)
            return self.clone_vm(source=source, name=name, node=node, full_clone=full_clone,
                                 failed_counter=failed_counter + 1)
        logger.info(f'waiting for "vm lock" to release on vmid {new_vm_id}')
        timeout = time.time() + 60
        new_vm_dict = {}
        while time.time() < timeout:
            new_vm_dict = self.get_vm_by_id(new_vm_id)
            if new_vm_dict:
                if new_vm_dict.get('vmid') and not new_vm_dict.get('lock', ''):
                    break
            else:
                time.sleep(5)
        if not new_vm_dict:
            logger.error('Something went wrong. Failed to retrieve the new vm details')
            return {}

        logger.debug(f'{new_vm_dict = }')
        time.sleep(10)  # Had issues where vm was still locked

        # New Vm created. Checking for node migration request
        new_vm_dict = self.migrate_vm_to_node(
            vm_id=new_vm_id, node_name=node)
        self.update_output_file(new_vm_dict)
        return new_vm_dict

    def migrate_vm_to_node(self, vm_id, node_name):
        """Migrate vm to a new node

        :param vm_id: Vm id
        :param node_name: Requested new node for vm
        :return: Vm dict
        """
        vm_dict = self.get_vm_by_id(vm_id=vm_id)
        assert vm_dict, f'No matching vm for the given vm id {vm_id}'
        if node_name == vm_dict['node']:
            logger.debug(f'vm {vm_id} already on node {node_name}')
            return vm_dict
        logger.info(f"Migrating vm {vm_id} to node {node_name}")
        try:
            task_obj = self.nodes(vm_dict['node']).qemu(vm_id).migrate.create(target=node_name)
            assert self.wait_for_task(
                task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)
        except Exception:
            logger.warning(f'Failed to migrate vm {vm_id} to node {node_name}. will retry after 1 minute')
            time.sleep(60)
            try:
                task_obj = self.nodes(vm_dict['node']).qemu(vm_dict['vmid']).migrate.create(target=node_name)
                assert self.wait_for_task(
                    task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)
            except Exception as ex2:
                logger.error(f'Failed to migrate vm {vm_id} to node {node_name} for Exception: {ex2}')
        timeout = time.time() + 60 * 2
        new_vm_dict = {}
        while time.time() < timeout:
            new_vms = self.get_vms(vm_id=vm_id)
            if not new_vms:
                time.sleep(5)
                continue
            new_vm_dict = new_vms[0]
            if new_vm_dict['node'] == node_name:
                return new_vm_dict
            else:
                time.sleep(10)
        else:
            logger.error('Something went wrong. Failed to detect the migration within 2 minutes')
            return new_vm_dict

    def get_vms_by_name(self, vm_name: str) -> List:
        """Returns a list of vms with matching name"""
        return self.get_vms(vm_name=vm_name)

    def get_vm_by_id(self, vm_id: int) -> Dict:
        """Returns vm dict matching the given vmid"""
        res = self.get_vms(vm_id=vm_id)
        if res:
            return res[0]
        else:
            return {}

    def get_vms(self, vm_id=0, vm_name='', vm_dict=None):
        """Returns a full list of vms, or list with matching vms by id or name"""
        vm_id = int(vm_id)
        try:
            if vm_dict:
                vm_id = vm_dict['vmid']
            vm_list = self.cluster.resources.get(type='vm')
            if vm_id:
                for i in vm_list:
                    if i['vmid'] == vm_id:
                        return [i]
            elif vm_name:
                return [i for i in vm_list if i.get('name') == vm_name]
            else:
                return vm_list
        except ConnectionError as exx:
            logger.exception(exx)
        return []

    def get_nodes(self):
        return self.cluster.resources.get(type='node')

    def select_node_for_new_vm(self):
        """Selects a node with capacity for a new vm and return its name"""
        nodes_list = self.get_nodes()
        random.shuffle(nodes_list)
        for node in nodes_list:
            mem_percent = node['mem'] / node['maxmem'] * 100
            cpu_percent = node['cpu'] * 100
            print(f"{node['node']}: {mem_percent=} | {cpu_percent=}")
            if mem_percent < 85 and cpu_percent <= 85:
                return node['node']
        else:
            time.sleep(60)  # time before retry
            return self.select_node_for_new_vm()

    def get_first_free_vm_id(self) -> int:
        """Returns the first vmid not assigned to any existing vm"""
        return int(self.cluster.nextid.get())


    def shutdown_vm(self, vm_id):
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        vm_id = vm_dict['vmid']
        vm_name = vm_dict['name']
        logger.info(f'Attempting to shut down vm {vm_name}:{vm_id}')
        try:
            task_obj = self.nodes(vm_dict['node']).qemu(vm_dict['vmid']).status.shutdown.create()
            assert self.wait_for_task(
                task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)
        except Exception as ex:
            logger.error(ex)
            return self.stop_vm(vm_id=vm_id)
        expected_status = 'stopped'
        timeout = time.time() + 40
        new_vm_dict = {}
        while time.time() < timeout:
            new_vm_dict = self.get_vm_by_id(vm_id=vm_id)
            if new_vm_dict['status'] == expected_status:
                return new_vm_dict
            else:
                time.sleep(10)
        else:
            logger.error(
                f'Something went wrong. Failed to detect expected state {expected_status} within 40 seconds')
            return new_vm_dict

    def reset_vm(self, vm_id):
        """Restart vm"""
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        logger.info(f"Restarting vm {vm_dict['vmid']}:{vm_dict['name']}")
        for i in range(3):
            try:
                logger.info(f"Restarting vm {vm_id}:{vm_dict['name']}. Attempt {i + 1}/3")
                task_obj = self.nodes(vm_dict['node']).qemu(vm_dict['vmid']).status.reset.create()
                assert self.wait_for_task(
                    task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60 * 2)
                logger.debug('Vm starting...')
                time.sleep(5)
                break
            except Exception as ex:
                logger.error(ex)
                time.sleep(10)
        return self.wait_for_ip(vm_id=vm_id)

    def delete_vm(self, vm_id, purge_hd=True):
        """Deletes the given vm by name or id

        :param vm_id: Vm ID
        :param purge_hd: True to purge the hard drive volume
        :return: True if successfully deleted
        """
        new_vm_dict = self.stop_vm(vm_id=vm_id)  # raise AssertionError if not found
        if new_vm_dict['status'] != 'stopped':
            logger.debug('Retry to stop vm after 10 seconds')
            time.sleep(10)
            new_vm_dict = self.stop_vm(vm_id=vm_id)
            assert new_vm_dict['status'] == 'stopped', f'Failed to stop vm a second time.\nvm_dict: {new_vm_dict}'
        vm_id = new_vm_dict['vmid']
        vm_node = new_vm_dict['node']
        vm_name = new_vm_dict['name']
        logger.info(f"Deleting vm {vm_id} {vm_name}")
        task_obj = self.nodes(vm_node).qemu(vm_id).delete(purge=int(purge_hd))
        assert self.wait_for_task(
            task_obj=task_obj, node=new_vm_dict['node'], task_owner=f'{new_vm_dict['name']}:{vm_id}', timeout=60)
        timeout = time.time() + 60
        vm = {}
        while time.time() < timeout:
            time.sleep(10)
            vm = self.get_vm_by_id(vm_id=vm_id)
            if not vm:
                return True
        logger.error('Failed to detect the vm was removed within 60 seconds. Check for lock state')
        logger.debug(f'{vm = }')
        return False

    def start_vm(self, vm_id):
        """Starts vm"""
        expected_status = 'running'
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        vm_id = vm_dict['vmid']
        if vm_dict['status'] == expected_status:
            return self.wait_for_ip(vm_id=vm_id)
        for i in range(3):
            try:
                logger.info(f"Starting vm {vm_id}:{vm_dict['name']}. Attempt {i + 1}/3")
                task_obj = self.nodes(vm_dict['node']).qemu(vm_id).status.start.create()
                assert self.wait_for_task(
                    task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)
                # assert self.is_vm_running(vm_id=vm_id), 'vm is not running! retry.'
                break
            except Exception as ex:
                logger.error(ex)
                time.sleep(10)
        new_vm_dict = self.wait_for_ip(vm_id=vm_id)
        if new_vm_dict:
            time.sleep(30)  # Time for OS to fully load *DO NOT DELETE*
        return new_vm_dict

    def stop_vm(self, vm_id):
        """Stops vm by vm_id

        :param vm_id: Vm ID
        :return: New vm dict
        """
        expected_status = 'stopped'
        vm_dict = self.get_vm_by_id(vm_id)
        if not vm_dict:
            raise AssertionError(f'No matching vm for the given vm id {vm_id}')

        if vm_dict['status'] == expected_status:
            return vm_dict
        vm_id = vm_dict['vmid']
        vm_name = vm_dict['name']
        vm_node = vm_dict['node']
        for i in range(3):
            try:
                logger.info(f"Stopping vm {vm_id} {vm_name}. Attempt {i + 1}/3")
                task_obj = self.nodes(vm_node).qemu(vm_id).status.stop.create()
                assert self.wait_for_task(
                    task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)
                break
            except Exception as ex:
                logger.error(ex)
                time.sleep(10)
        timeout = time.time() + 40
        new_vm_dict = {}
        while time.time() < timeout:
            new_vm_dict = self.get_vm_by_id(vm_id=vm_id)
            if new_vm_dict['status'] == expected_status:
                return new_vm_dict
            else:
                time.sleep(10)
        else:
            logger.error(
                f'Something went wrong. Failed to detect expected state {expected_status} within 40 seconds')
            return new_vm_dict

    def get_snapshots(self, vm_id):
        """Returns a list of available snapshots from given vm

        :param vm_id: Vm ID
        :return: List of available snapshots
        """
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        snapshots = []
        for i in range(3):
            try:
                snapshots = self.nodes(vm_dict['node']).qemu(vm_dict['vmid']).snapshot.get()
                break
            except Exception as ex:
                logger.error(ex)
                time.sleep(10)
        return snapshots

    def create_snapshot(self, snapshot_name, vm_id, replace_existing=True):
        """Creates a snapshot on the given vm

        :param snapshot_name: Snapshot name
        :param vm_id: Vm ID
        :param replace_existing: Replace existing snapshot if already exist, rename new if False
        :return: New snapshot creation response
        """
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        vm_id = vm_dict['vmid']
        existing_snapshots = self.get_snapshots(vm_id=vm_id)
        name_exists = [snapshot for snapshot in existing_snapshots if snapshot["name"] == snapshot_name]
        if name_exists:
            if replace_existing:
                logger.debug('Old snapshot exists. Replacing existing snapshot')
                self.delete_snapshot(snapshot_name=snapshot_name, vm_id=vm_id)
                time.sleep(1)
            else:
                snapshot_name = f'{snapshot_name}{random.randint(1111, 9999)}'
                name_exists = [snapshot for snapshot in existing_snapshots if snapshot["name"] == snapshot_name]
                if name_exists:
                    snapshot_name = f'{snapshot_name}{random.randint(1111, 9999)}'
                logger.debug(f'Existing snapshot exists. Creating new snapshot with a new name: {snapshot_name}')
        task_obj = None
        for i in range(3):
            try:
                task_obj = self.nodes(vm_dict['node']).qemu(vm_id).snapshot.create(snapname=snapshot_name)
                break
            except Exception as ex:
                logger.error(ex)
                time.sleep(10)
        return self.wait_for_task(
            task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)

    def delete_snapshot(self, snapshot_name, vm_id):
        """Deletes the requested snapshot from the given vm

        :param snapshot_name: Snapshot name
        :param vm_id: Vm ID
        :return: New snapshot deletion response
        """
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        vm_id = vm_dict['vmid']
        snapshots = self.get_snapshots(vm_id=vm_id)
        if not [snapshot for snapshot in snapshots if snapshot["name"] == snapshot_name]:
            raise Exception(f'No matching snapshots for the given snapshot name {snapshot_name} in vm {vm_id}')
        task_obj = self.nodes(vm_dict['node']).qemu(vm_id).snapshot(snapshot_name).delete()
        return self.wait_for_task(
            task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)

    def revert_to_snapshot(self, snapshot_name, vm_id):
        """Reverts given vm to the given snapshot

        :param snapshot_name: Snapshot name. Leave empty to get the latest snapshot
        :param vm_id: Vm ID
        :return: New snapshot revert response
        """
        vms = self.get_vms(vm_id=vm_id)
        if not vms:
            raise Exception(f'No matching vm for the given vm id {vm_id}')
        vm_dict = vms[0]
        vm_id = vm_dict['vmid']
        snapshots = self.get_snapshots(vm_id=vm_id)
        if snapshot_name:
            if not [snapshot for snapshot in snapshots if snapshot["name"] == snapshot_name]:
                raise Exception(f'No matching snapshots for the given snapshot name {snapshot_name} in vm {vm_id}')
        else:
            matching_snaps = sorted([i for i in snapshots if i.get('snaptime')], key=lambda d: d['snaptime'],
                                    reverse=True)
            if matching_snaps:
                snapshot = matching_snaps[0]
                snapshot_name = snapshot["name"]
        task_obj = self.nodes(vm_dict['node']).qemu(vm_id).snapshot(snapshot_name).rollback().post()
        res = self.wait_for_task(
            task_obj=task_obj, node=vm_dict['node'], task_owner=f'{vm_id}:{vm_dict['name']}', timeout=60)
        time.sleep(6)
        return res

    def select_source_by_label(self, label):
        """Return the first matching template vm dict for the given label"""
        for template_name, template_dict in self.templates.items():
            if label.lower() in [i.lower() for i in template_dict.get('labels', [])]:
                return self.get_vms_by_name(template_name)
        logger.error(f'Failed to find a template matching the given label {label}')
        return None


    def get_and_log_vm_ips(self, vm_dict):
        """Calls the proxmox agent installed on the vm and asks for network interface data,
         filters out and logs all the IP addresses of the vm. Also dumps the list into a local file name vm_ips.txt.

        :param vm_dict: The vm_dict extracted from the list that gets returned from get_vms_by_name()
        """
        network_dict = self.nodes(vm_dict['node']).qemu(vm_dict['vmid']).agent.get('network-get-interfaces')
        vm_ips = []
        for network in network_dict.get('result', []) if network_dict else []:
            vm_ips.extend(network.get('ip-addresses', []))
        if vm_ips:
            logger.info(f'Got vm IP address list: {vm_ips}')
            with open('vm_ips.txt', 'w+') as results_file:
                results_file.write(json.dumps(vm_ips))
        return vm_ips

    def clone_vms(self, *vm_names):
        """Create vms from given labels"""
        vms = []
        for vm_name in vm_names:
            try:
                res = self.clone_vm(vm_name)
                vms.append(res)
            except Exception as e:
                logger.exception(e)
        return vms

    def vm_boot_cycle_to_refresh_ip(self, vm_id):
        self.start_vm(vm_id=vm_id)
        self.shutdown_vm(vm_id=vm_id)


    def update_output_file(self, vm_dict):
        """Updating the given vm_dict inside the self.clone_output_file"""
        logger.info(f"Updating vm {vm_dict['vmid']} in {self.clone_output_file}")
        if os.path.isfile(self.clone_output_file):
            with open(self.clone_output_file, 'r') as new_vms_file:
                out_dict = json.loads(new_vms_file.read())
                out_dict[str(vm_dict['vmid'])] = vm_dict
        else:
            out_dict = {str(vm_dict['vmid']): vm_dict}
        with open(self.clone_output_file, 'w') as new_vms_file:
            new_vms_file.write(json.dumps(out_dict, indent=4, default=str))

    def delete_vms_by_id(self, vm_ids):
        """Delete vms by ids"""
        successful = True
        for vm_id in vm_ids:
            try:
                if not self.delete_vm(vm_id=int(vm_id)):
                    successful = False
            except Exception as e:
                logger.exception(e)
                successful = False
        return successful

    def run_command(self, command, vm_id, timeout=60):
        """Execute command on a given vmid"""
        vm_dict = self.get_vm_by_id(vm_id)
        res = self.nodes(vm_dict['node']).qemu(vm_id).agent('exec').post(command=command)
        time.sleep(5)
        if isinstance(res, dict) and 'pid' in res:
            pid = res.get('pid')
            result = {}
            end_time = time.time() + timeout
            while time.time() <= end_time and not result.get('exited'):
                try:
                    result = self.nodes(vm_dict['node']).qemu(vm_id).agent('exec-status').get(pid=pid)
                    logger.debug(f"Command Output: {result}")
                except Exception as e:
                    logger.error(e)
                time.sleep(5)
            return result
        return None

    def get_ipv4(self, vm_id):
        """Get a valid ipv4 address from the guest vm"""
        vm_dict = self.get_vm_by_id(vm_id)
        vm_name = vm_dict['name']
        ip_list = self.get_and_log_vm_ips(vm_dict)
        logger.debug(f'vm {vm_name}:{vm_id} {ip_list = }')
        ipl = [i['ip-address'] for i in ip_list if 128 > i['prefix'] > 8
               and i['ip-address-type'] == 'ipv4'
               and i['ip-address'] not in ['100.64.0.1', '127.0.0.1']
               and not i['ip-address'].startswith('169.254')
               and not i['ip-address'].startswith('100.96')
               ]
        if ipl and (ipl[0] == '127.0.0.1' or ipl[0].startswith('169.254')):
            logger.error(f'vm {vm_name}:{vm_id} does not have a valid IP address')
            return ''
        if ipl:
            logger.info(f'vm {vm_name}:{vm_id} IP address: {ipl[0]}')
            return ipl[0]
        return ''

    def run_command_by_ssh(self, vm_id, command):
        """Send ssh command to vm"""
        ipv4 = self.get_ipv4(vm_id=vm_id)
        assert ipv4, 'Vm does not have a valid IP address! ABORTING!'
        return run_commands(
            server=ipv4,
            username='user',
            password='1qaz@WSX',
            commands=[command]
        )

    def is_vm_running(self, vm_id):
        """Return True if vm is in state "running" """
        vm_state = 'N/A'
        try:
            vm_dict = self.get_vm_by_id(vm_id=vm_id)
            vm_state = vm_dict.get('state', 'N/A')
        except Exception as e:
            logger.warning(e)
        logger.debug(f'vm state: {vm_state}')
        return vm_state == 'running'

    def wait_for_ip(self, vm_id, timeout=120):
        """Checking if the OS is loaded by trying to get IP address

        :param vm_id: vmid
        :param timeout: Timeout in seconds
        :return: Vm dict
        """
        if self.is_vm_running:
            logger.info(f'Vm {vm_id} is running. Waiting for the OS to boot')
        else:
            return None
        new_vm_dict = self.get_vm_by_id(vm_id=vm_id)
        end_time = time.time() + timeout
        while time.time() <= end_time:
            try:
                logger.debug(f'Checking vmid {vm_id} OS for ip')
                # print(self.get_and_log_vm_ips(new_vm_dict))
                if self.get_ipv4(vm_id):
                    break  # Successfully got an IP address
                else:
                    time.sleep(5)
            except Exception as e:
                logger.warning(e)
                time.sleep(30)
        else:
            logger.error(f'Something went wrong. Failed to detect state change within {timeout} seconds')

        return new_vm_dict


def cleanup_temp_proxmox_vms(only_stopped_vms=True):
    """Delete auto deployed proxmox vms

    :param only_stopped_vms: Delete only vms that are "stopped"
    :return: List of deleted vm names
    """
    pm = Proxmox()
    names_to_delete = ['proxmoxWindows10', 'proxmoxWindows11', 'proxmoxVentura', 'proxmoxSonoma', 'proxmoxSequoia',
                       'windows10', 'windows11', 'ventura', 'sonoma', 'sequoia']
    deleted_vms = {}
    for name in names_to_delete:
        vms = pm.get_vms(vm_name=name)
        for vm in vms:
            vmid = vm['vmid']
            if only_stopped_vms:
                if vm['status'] == 'stopped':
                    deleted_vms[vmid] = vm['name']
                    pm.delete_vms_by_id([vmid])
            else:
                deleted_vms[vmid] = vm['name']
                pm.delete_vms_by_id([vmid])
    logger.info(f'Deleted {len(deleted_vms)} VMs: {deleted_vms}')
    return deleted_vms

def delete_all_permanent_jenkins_slaves_proxmox_vms(
        clean_list=('windows10', 'windows11', 'ventura', 'sonoma', 'sequoia'),
        only_stopped_vms=False):
    """Delete all proxmox vms by regex that match the pattern: 'proxmox<vmid><Capitalize OS name>'

    :param clean_list: List of OS names to clean. Will be used for the pattern search
    :param only_stopped_vms: Delete only vms that are "stopped"
    :return: List of deleted vm names
    """
    deleted_vms = {}
    pm = Proxmox()
    vms = pm.get_vms()
    for vm in vms:
        vmid = vm['vmid']
        known_pattern = f'proxmox{vmid}'
        for os_name in clean_list:
            if vm['name'] == f'{known_pattern}{os_name.capitalize()}':
                if only_stopped_vms:
                    if vm['status'] == 'stopped':
                        deleted_vms[vmid] = vm['name']
                        pm.delete_vms_by_id([vmid])
                else:
                    deleted_vms[vmid] = vm['name']
                    pm.delete_vms_by_id([vmid])
    logger.info(f'Deleted {len(deleted_vms)} VMs: {deleted_vms}')
    return deleted_vms

if __name__ == '__main__':
    cli_main_for_class(Proxmox)