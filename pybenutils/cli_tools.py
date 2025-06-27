import sys

from typing import List


def smart_cmd_input_eval(input_params: List):
    """Evaluate the given input list (sys.argv[:]) and returns (unnamed_params_list, named_params_dict)"""
    unnamed_params_list = []
    named_params_dict = {}
    for i in input_params:
        if '=' in i:
            key = i.split('=', 1)[0]
            value = i.split('=', 1)[-1]
            if value.lower() in ['yes', 'true']:
                value = True
            elif value.lower() in ['no', 'false']:
                value = False
            try:
                value = eval(value)
            except Exception:
                pass
            named_params_dict[key] = value
        else:
            unnamed_params_list.append(i)
    return unnamed_params_list, named_params_dict


def cli_main_for_class(cls_obj):
    """Passing sys.argv input params to given class to enable CLI interface"""
    print(sys.argv)

    help_str = f"This lib provides mechanism to execute {cls_obj.__name__} class methods from command line.\n" \
               f"Use 'dir' to get list of all public {cls_obj.__name__} class methods.\n" \
               "Use 'help' or 'help [methods]' for help on each method."
    if len(sys.argv) == 1:
        print("No method given to execute.", file=sys.stderr)
        print(help_str)
    else:
        cls = cls_obj()
        command = sys.argv[1]
        parameters, parameters_dict = smart_cmd_input_eval(sys.argv[2:])

        if command in ['ls', 'dir', '--dir', '-d']:
            print([func for func in dir(cls) if callable(getattr(cls, func)) and not func.startswith("__")])
        elif command in ['help', '--help', '-h']:
            if len(parameters) == 0:
                help(cls)
            else:
                help(getattr(cls, parameters[0]))
        elif command in ['doc', '--doc']:
            for func in [func for func in dir(cls) if callable(getattr(cls, func)) and not func.startswith("__")]:
                print(func, func.__doc__)
        elif command.startswith("-"):
            print("No supported flags.", file=sys.stderr)
            print(help_str)
        elif not hasattr(cls, command):
            print(f"Class {cls_obj.__name__} has no method {command}.", file=sys.stderr)
            print(help_str)
        elif not callable(getattr(cls, command)):
            print(f"{command = } is not callable method of class {cls_obj.__name__}.", file=sys.stderr)
            print(help_str)
        else:
            command_function = getattr(cls, command)
            assert command_function, f"Internal error. {command_function = }"
            print(command_function(*parameters, **parameters_dict))