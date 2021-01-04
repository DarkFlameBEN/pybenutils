import os
import time
import json
import paramiko
import tempfile
import argparse
import threading


results_list = []
example_dict = {
    "connections": [
        {
            "host": "192.168.0.10",  # The target server ip
            "host_user": "qa",  # The target server local admin user name
            "host_pass": "1234",  # The target server local admin user password
            "cmd_list": [
                "python3 -m pip install pip -U",
                "echo 1234 > pass.txt",
                "GET_FILE pass.txt",  # Copy the requested file from the mac vm to the windows vm
                # Notice: Everything in "/tmp" directory will be lost when the machine shuts down
            ]
        }
    ]
}


class SshHelper:
    def __init__(self, host, user_name, password):
        self.user = user_name
        self.password = password
        self.host = host
        self.port = 22
        self.timeout = 120
        self.bufsize = -1
        self.client = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(hostname=self.host, port=self.port, username=self.user, password=self.password,
                            banner_timeout=10)

    def run(self, command):
        if not self.client:
            self.connect()
        chan = self.client.get_transport().open_session()
        chan.settimeout(self.timeout)
        chan.set_combine_stderr(True)
        chan.get_pty()
        chan.exec_command(command)
        stdout = chan.makefile('r', self.bufsize)
        stdout_text = stdout.read()
        status = int(chan.recv_exit_status())
        return stdout_text, status

    def run_in_terminal(self, command, outputfile='outfile'):
        tempdir = tempfile.gettempdir()  # prints the current temporary directory
        temp_file_name = os.path.join(tempdir, 't_{ts}.txt'.format(ts=str(time.time()).replace('.', '')))
        with open(temp_file_name, mode='w+') as f:
            f.write(r'{cmd} 2>&1 | tee {output} ;'.format(cmd=command, output=outputfile) + '\n')
            f.write("osascript -e 'tell application \"Terminal\" to quit' ;" + '\n')

            f.seek(0)  # return to beginning of file
            print(f.read())  # reads data back from the file

        try:
            if not self.client:
                self.connect()

            sftp = self.client.open_sftp()
            sftp.put(temp_file_name, '/tmp/tmp.sh')

            chan = self.client.get_transport().open_session()
            chan.settimeout(self.timeout)
            chan.set_combine_stderr(True)
            chan.get_pty()
            chan.exec_command(r'chmod +x /tmp/tmp.sh ;'
                              r'open -W -a Terminal /tmp/tmp.sh ;'.format(cmd=command))
            # stdout = chan.makefile('r', self.bufsize)
            # stdout_text = stdout.read()
            status = int(chan.recv_exit_status())

            stdout_text, stam = self.run(r'cat {output}'.format(output=outputfile))

            return stdout_text, status
        finally:
            self.close()

    def close(self):
        self.client.close()

    def copy_to_remote(self, source, destination):
        """ Copy file from local to remote

        :param source: local file
        :param destination: Full path on remote machine
        """
        if not self.client:
            self.connect()
        sftp = self.client.open_sftp()
        sftp.put(os.path.realpath(source), destination)
        self.close()

    def get_from_remote(self, source, destination):
        if not self.client:
            self.connect()
        sftp = self.client.open_sftp()
        sftp.get(source, destination)
        self.close()


def run_cmd(conf):
    global results_list
    thread_log = '---THREAD_START---\n'
    for idx, cmd in enumerate(conf['cmd_list']):
        thread_log += '*****\n'
        cmd = str(cmd).replace("'", "\\'")
        thread_log += 'Running cmd: {}\n'.format(cmd)
        open_connection = SshHelper(host=conf['host'], user_name=conf['host_user'], password=conf['host_pass'])
        status = 'DONE'
        output = ''
        if cmd.startswith('COPY_FILE'):
            thread_log += 'Trying to copy {s} to {t}\n'.format(s=cmd.split()[1], t=cmd.split()[2])
            try:
                open_connection.copy_to_remote(source=cmd.split()[1], destination=cmd.split()[2])
            except Exception as err:
                thread_log += 'Failed to perform copy function for error: {e}\n'.format(e=err)
        elif cmd.startswith('GET_FILE'):
            thread_log += 'Trying to copy {s} to {t}\n'.format(s=cmd.split()[1], t=cmd.split()[2])
            try:
                open_connection.get_from_remote(source=cmd.split()[1], destination=cmd.split()[2])
            except Exception as err2:
                thread_log += 'Failed to perform get function for error: {e}\n'.format(e=err2)
        else:
            try:
                output_file_path = '/Automation/output_{ind}.txt'.format(ind=idx)
                output, status = open_connection.run_in_terminal(cmd, outputfile=output_file_path)
            except Exception as err3:
                thread_log += 'Failed to perform run command function for error: {e}\n'.format(e=err3)
                thread_log += 'Stopping the commands flow due to connection problem\n'
                break
        thread_log += 'Finished with status code: {s}. Run-time log: {log}\n'.format(s=status, log=str(output))

        time.sleep(5)
    thread_log += '---THREAD_END---\n'
    with open(args.out, 'w+') as out_file:
        out_file.write(thread_log)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mac script activator trough SSH connection')
    parser.add_argument('-c', '--config_file',
                        help=f'Parameters json file for the ssh connection\n{json.dumps(example_dict)}',
                        required=False,
                        default='')
    parser.add_argument('-o', '--out', help='Output log file path', required=False, nargs='?',
                        default='output_{ts}.txt'.format(ts=str(time.time()).replace('.', '')))
    args = parser.parse_args()

    if not os.path.isfile(args.config_file):
        print(f'Missing input "--config_file" Please run {__file__} --help to see input details.\n'
              f'Example config file:\n{json.dumps(example_dict, indent=4)}')
        exit(1)

    with open(args.config_file, 'r') as config_file_source:
        ssh_config_dict = json.load(config_file_source)
    with open(args.out, 'w') as output_file:
        output_file.write('')
    threads = []
    for connection in ssh_config_dict['connections']:
        t = threading.Thread(target=run_cmd, args=(connection,))
        threads.append(t)
        t.start()
    for thread in threads:
        thread.join()
