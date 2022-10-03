import sys
from pybenutils.autogui.auto_gui_cls import AutoGui
import argparse

print(sys.argv)
parser = argparse.ArgumentParser(description='PyBenAutoGui - Class to automate cross platform GUI interactions.')
parser.add_argument('-t', '--title', help='Window title')
parser.add_argument('-a', '--app_path', help='Application/Exe path')
parser.add_argument('-b', '--pywinauto_backend', default='uia', required=False,
                    help='A name of used back-end in Windows OS (values: "win32", "uia")')
parser.add_argument('-c', '--command', default='uia',
                    help='Function name to execute in the AutoGui Class')
args = parser.parse_known_args()
title = args[0].title
app_path = args[0].app_path
pywinauto_backend = args[0].pywinauto_backend
command = args[0].command
parameters = args[1]
command_function = getattr(AutoGui(title=title, app_path=app_path, pywinauto_backend=pywinauto_backend), command)
if command_function:
    print(command_function(*parameters))
