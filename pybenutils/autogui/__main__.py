import sys
import argparse

from pybenutils.autogui.auto_gui_cls import AutoGui
from pybenutils.cli_tools import smart_cmd_input_eval

print(sys.argv)
parser = argparse.ArgumentParser(description='PyBenAutoGui - Class to automate cross platform GUI interactions.')
parser.add_argument('-t', '--title', help='Window title')
parser.add_argument('-a', '--app_path', help='Application/Exe path')
parser.add_argument('-b', '--pywinauto_backend', default='uia', required=False,
                    help='A name of used back-end in Windows OS (values: "win32", "uia")')
parser.add_argument('-c', '--command', help='Function name to execute in the AutoGui Class')
parser.add_argument('-eh', '--extra_help', help='Display extra help about the class and its functions', required=False,
                    default=False, action=argparse.BooleanOptionalAction)
args = parser.parse_known_args()
title = args[0].title
app_path = args[0].app_path
pywinauto_backend = args[0].pywinauto_backend
command = args[0].command
parameters = args[1]
extra_help = args[0].extra_help

if extra_help:
    if command:
        help(getattr(AutoGui, command))
    else:
        help(AutoGui)
    exit(0)

command_function = getattr(AutoGui(title=title, app_path=app_path, pywinauto_backend=pywinauto_backend), command)
if command_function:
    parameters, parameters_dict = smart_cmd_input_eval(parameters)
    print(command_function(*parameters, **parameters_dict))
