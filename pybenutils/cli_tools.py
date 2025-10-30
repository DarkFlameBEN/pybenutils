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


def execute_class(cls_obj, class_params, args=()):
    help_str = f"This lib provides mechanism to execute {cls_obj.__name__} class methods from command line.\n" \
               f"Use 'ls' or 'dir' to get list of all public {cls_obj.__name__} class methods.\n" \
               "Use 'help' or 'help [methods]' for help on each method."

    command = args[0] if args else ''
    parameters, parameters_dict = smart_cmd_input_eval(args[1:])

    if command in ['ls', 'dir', '--dir', '-d']:
        print([func for func in dir(cls_obj) if callable(getattr(cls_obj, func)) and not func.startswith("__")])
        return
    elif command in ['help', '--help', '-h']:
        if len(parameters) == 0:
            help(cls_obj)
        else:
            help(getattr(cls_obj, parameters[0]))
        return
    elif command in ['doc', '--doc']:
        for func in [func for func in dir(cls_obj) if callable(getattr(cls_obj, func)) and not func.startswith("__")]:
            print(func, func.__doc__)
        return
    elif command.startswith("-"):
        print("No supported flags.", file=sys.stderr)
        print(help_str)
        return

    # Instantiate the class
    print(f'Initiating class {cls_obj.__name__} with params: {class_params}')
    cls = cls_obj(**class_params)

    # Handle nested property.method pattern
    sub_command = None
    if len(args) > 1:
        # If first token is property (non-callable but exists)
        attr = getattr(cls, command, None)
        if attr is not None and not callable(attr) and len(args) > 1:
            sub_command = args[1]
            parameters, parameters_dict = smart_cmd_input_eval(args[2:])
            target_obj = attr
        else:
            target_obj = cls
    else:
        target_obj = cls

    # Determine final callable
    method_name = sub_command or command
    if not hasattr(target_obj, method_name):
        print(f"{target_obj.__class__.__name__} has no method '{method_name}'.", file=sys.stderr)
        print(help_str)
        return

    method = getattr(target_obj, method_name)

    if not callable(method):
        print(f"'{method_name}' is not callable.", file=sys.stderr)
        print(help_str)
        return

    if parameters and parameters[0] in ['--help', '-h']:
        help(method)
        return

    # Execute method
    print(f'Executing {method_name} with params: {parameters} and named params: {parameters_dict}')
    print(method(*parameters, **parameters_dict))


def cli_main_for_class(cls_obj):
    print(sys.argv)

    class_params = {}
    for i in range(1, len(sys.argv)):
        i_parameters, i_parameters_dict = smart_cmd_input_eval([sys.argv[i]])
        class_params.update(i_parameters_dict)
        if i_parameters:
            return execute_class(cls_obj=cls_obj, class_params=class_params, args=sys.argv[i:])
    return execute_class(cls_obj=cls_obj, class_params=class_params)
