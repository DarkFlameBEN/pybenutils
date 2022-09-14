import sys
from pybenutils.autogui.auto_gui_cls import AutoGui

print(sys.argv)

if len(sys.argv) > 1:
    title = sys.argv[1]
    app_path = sys.argv[2]
    command = sys.argv[3]
    parameters = sys.argv[4:]
    command_function = getattr(AutoGui(title, app_path), command)
    if command_function:
        print(command_function(*parameters))
