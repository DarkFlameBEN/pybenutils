import platform
import sys
import json
import argparse
from typing import List
from scp import SCPClient

from pybenutils.useful import str2bool

arch = platform.machine().lower()
ARM_PROCESSOR = "arm" in arch or "aarch" in arch
if not ARM_PROCESSOR:
    from paramiko import SSHClient, AutoAddPolicy

from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


def run_commands(server: str,
                 username: str,
                 password: str,
                 commands: List[str],
                 stop_on_exception=False,
                 stop_on_error=False):
    """Execute the given commands through ssh connection

     Special commands:
      - RECURSIVE-PUT file_path/folder_path [To local_path] - Copy the target from remote to local recursively
      - GET file_path/folder_path [To local_path] - Copy the target from remote to local
      - RECURSIVE-PUT file_path/folder_path TO remote_path - Sends file from local to remote recursively
      - PUT file_path/folder_path TO remote_path - Sends file from local to remote

    :param server: Remote server ip
    :param username: Remote server username
    :param password: Remote server password
    :param commands: List of commands to execute
    :param stop_on_exception: Will stop executing commands if an exception occurred
    :param stop_on_error: Will stop executing commands if an execution returned an stderr string
    :return: List of return objects [{'ssh_stdin': str, 'ssh_stdout': str, 'ssh_stderr': str}]
    """
    transition_responses = []
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())
    print(f'Connecting to {server}')
    ssh.connect(server, username=username, password=password)
    for command in commands:
        try:
            if command.startswith('RECURSIVE-GET') or command.startswith('GET'):
                with SCPClient(ssh.get_transport()) as scp:
                    source = command.split(' GET ', 1)[-1].split(' TO ', 1)[0].strip()
                    target = command.split(' TO ', 1)[-1].strip()
                    scp.get(source, target, recursive=command.startswith('RECURSIVE-'))
                    transition_responses.append({'ssh_stdin': command,
                                                 'ssh_stdout': 'success',
                                                 'ssh_stderr': ''})
                    print(transition_responses[-1])
            elif command.startswith('RECURSIVE-PUT') or command.startswith('PUT'):
                with SCPClient(ssh.get_transport()) as scp:
                    source = command.split('PUT', 1)[-1].split(' TO ')[0].strip()
                    target = command.split('PUT', 1)[-1].split(' TO ')[-1].strip()
                    scp.put(source, target, recursive=command.startswith('RECURSIVE-'))
                    transition_responses.append({'ssh_stdin': command,
                                                 'ssh_stdout': 'success',
                                                 'ssh_stderr': ''})
                    print(transition_responses[-1])
            else:
                ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
                stdout = ssh_stdout.read().decode()
                stderr = ssh_stderr.read().decode()
                transition_responses.append({'ssh_stdin': command,
                                             'ssh_stdout': stdout,
                                             'ssh_stderr': stderr})
                try:
                    print(transition_responses[-1])
                except Exception as e:
                    print(e)
                if stop_on_error and stderr:
                    break
        except Exception as ex:
            transition_responses.append({'ssh_stdin': command, 'ssh_stdout': '', 'ssh_stderr': str(ex)})
            print(transition_responses[-1])
            if stop_on_exception:
                break
    return transition_responses


if __name__ == '__main__':
    print(sys.argv)
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', nargs='?', default='', required=False,
                        help='Get configuration from json file')
    parser.add_argument('-s', '--server', nargs='?', default='', required=False,
                        help='Remote server ip')
    parser.add_argument('-u', '--username', nargs='?', default='', required=False,
                        help='Remote server username')
    parser.add_argument('-p', '--password', nargs='?', default='', required=False,
                        help='Remote server password')
    parser.add_argument('-c', '--commands', nargs='*', default=[], required=False,
                        help='List of commands to execute')
    parser.add_argument('-sexc', '--stop_on_exception', type=str2bool, nargs='?', default='', required=False,
                        help='Will stop executing commands if an exception occurred')
    parser.add_argument('-serr', '--stop_on_error', nargs='?', type=str2bool, default='', required=False,
                        help='Will stop executing commands if an exception occurred')
    parser.add_argument('-o', '--output', nargs='?', default='ssh_output.json', required=False,
                        help='output file path')
    args, remaining_args = parser.parse_known_args()
    if args.file:
        with open(args.file, 'r') as json_file:
            configurations = json.loads(json_file.read())
    for arg in ['server', 'username', 'password', 'commands', 'stop_on_exception', 'stop_on_error']:
        if args.__getattribute__(arg):
            configurations[arg] = args.__getattribute__(arg)

    output_list = run_commands(**configurations)

    with open(args.output, 'w') as out_file:
        out_file.write(json.dumps(output_list, indent=4, default=str))
