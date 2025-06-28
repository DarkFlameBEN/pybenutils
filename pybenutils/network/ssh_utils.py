import platform
import sys
import json
import argparse
from typing import List, Union
from scp import SCPClient
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
    """Execute the given commands trough ssh connection

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
                stdout = ssh_stdout.readlines()
                transition_responses.append({'ssh_stdin': command,
                                             'ssh_stdout': stdout,
                                             'ssh_stderr': 'Not Implemented'})
                try:
                    print(transition_responses[-1])
                except Exception as e:
                    print(e)
                if stop_on_error and ssh_stderr:
                    break
        except Exception as ex:
            transition_responses.append({'ssh_stdin': command, 'ssh_stdout': '', 'ssh_stderr': str(ex)})
            print(transition_responses[-1])
            if stop_on_exception:
                break
    return transition_responses


def run_ssh_command(server: str, username: str, password: str, command: str, timeout: Union[int, None] = None, ignore_exit_code: bool = False) -> None:
    """
    Execute a single command on a remote server via SSH and log the output.

    :param server: Remote server IP or hostname.
    :param username: SSH username.
    :param password: SSH password.
    :param command: Command to execute.
    :param timeout: Timeout for the command execution in seconds.
    :param ignore_exit_code: If True, do not raise an exception for non-zero exit codes.
    """
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())

    try:
        logger.info(f"Connecting via SSH to {server} as {username}")
        ssh.connect(server, username=username, password=password, timeout=timeout)

        logger.info(f"[{server}] Executing command: {command}")
        _, stdout, stderr = ssh.exec_command(command, timeout=timeout)

        # Log stdout incrementally
        for line in stdout:
            logger.info(line.strip())

        # Log stderr incrementally
        for line in stderr:
            logger.error(line.strip())

        # Get the exit status
        exit_status = stdout.channel.recv_exit_status()
        logger.info(f"[{server}] Command executed with exit status: {exit_status}")

        if exit_status != 0 and not ignore_exit_code:
            raise RuntimeError(f"Command '{command}' failed with exit code {exit_status}")
    except Exception as e:
        logger.error(f"SSHException: {str(e)}")
        raise
    finally:
        ssh.close()
        logger.info(f"SSH connection to {server} closed")


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
