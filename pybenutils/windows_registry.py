import os
import sys

from pybenutils.utils_logger import config_logger


if sys.platform == 'win32':
    from winreg import *
    import winreg

logger = config_logger.get_logger()


def reg_mapper():
    return {'HKEY_LOCAL_MACHINE': winreg.HKEY_LOCAL_MACHINE,
            'HKEY_CURRENT_USER': winreg.HKEY_CURRENT_USER,
            'HKEY_CLASSES_ROOT': winreg.HKEY_CLASSES_ROOT,
            'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKCU': winreg.HKEY_CURRENT_USER,
            'HKCR': winreg.HKEY_CLASSES_ROOT}


def get_os_registry_architecture():
    """Use this func to get a corrected path to access your registry files

    :return: win os 32 or 64 windows registry access
    """
    return winreg.KEY_WOW64_64KEY if 'PROGRAMFILES(X86)' in os.environ else winreg.KEY_WOW64_32KEY


def validate_registry_key(string_path):
    """Validate that key has correct syntax

    :param string_path: full key path
    """
    if string_path.split('\\')[0] not in reg_mapper():
        raise ValueError('"{}" is an invalid registry root'.format(string_path.split('\\')[0]))


def is_key_exists(root_key, path):
    """check if key exists

    :param root_key: root HKEY
    :param path: key path
    :return: True / False
    :rtype: bool
    """
    aReg = ConnectRegistry(None, reg_mapper()[root_key])

    exists = True
    try:
        aKey = winreg.OpenKey(aReg, path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))
        winreg.CloseKey(aReg)
        winreg.CloseKey(aKey)
    except WindowsError:
        exists = False
    return exists


def set_registry_key(root_key, key):
    """Creates a new key or set an existing subkey. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param key: key path
    :type root_key: str
    :type key: str
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])

    counter = 1
    split_key = key.split('\\')
    try:
        while counter <= len(split_key):
            inner_key = '\\'.join(split_key[:counter])
            if not is_key_exists(root_key, inner_key):
                logger.info('creating the registry key: {root}\\{key}'.format(root=root_key, key=inner_key))
                aKey = winreg.OpenKey(aReg, os.path.dirname(inner_key), 0,
                                       (get_os_registry_architecture() | winreg.KEY_ALL_ACCESS))

                winreg.CreateKeyEx(aKey, os.path.basename(inner_key), 0, winreg.KEY_ALL_ACCESS)
                winreg.CloseKey(aKey)
                counter += 1
            else:
                counter += 1
        winreg.CloseKey(aReg)
    except WindowsError as err:
        logger.error(err)
    if not is_key_exists(root_key, key):
        logger.warning('failed to create the key: {root}\\{key}'.format(root=root_key, key=key))


def delete_registry_key(root_key, path):
    """Delete key from path. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param path: key path
    :type root_key: str
    :type path: str
    """
    key = os.path.basename(path)
    path = os.path.dirname(path)

    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))
    winreg.DeleteKey(aKey, key)
    winreg.CloseKey(aReg)
    winreg.CloseKey(aKey)


def get_registry_value(root_key, path, value):
    """Get data from string value. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param path: get key path name
    :param value: value name
    :return: value data
    :type root_key: str
    :type path: str
    :type value: str
    :rtype: str
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    value_dict = {}
    noOfValues = winreg.QueryInfoKey(aKey)[1]
    for i in range(0, noOfValues):
        value_dict[winreg.EnumValue(aKey, i)[0].lower()] = winreg.EnumValue(aKey, i)[1]
    winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)
    if value.lower() in value_dict:
        return value_dict[value.lower()]
    else:
        return


def set_registry_value(root_key, key, value, data):
    """Set value-data pair on key. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param key: key path
    :param value: value name
    :param data: string to set
    :type root_key: str
    :type key: str
    :type value: str
    :type data: str
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, key, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    winreg.SetValueEx(aKey, value, 0, winreg.REG_SZ, data)
    winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)


def get_registry_key_values(root_key, path):
    """Get data from key value. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param path: get key path name
    :return: string_name, data and type_id
    :type root_key: str
    :type path: str
    :rtype: dict
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    values_dict = [{'string_name': winreg.EnumValue(aKey, i)[0],
                    'data': winreg.EnumValue(aKey, i)[1],
                    'type_id': winreg.EnumValue(aKey, i)[2]}
                   for i in range(0, winreg.QueryInfoKey(aKey)[1])]

    winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)
    return values_dict


def delete_registry_value(root_key, path, value):
    """Deletes value name. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param path: key path
    :param value: value name
    :type root_key: str
    :type path: str
    :type value: str
    """
    aKey = winreg.OpenKey(reg_mapper()[root_key], path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    winreg.DeleteValue(aKey, value)
    winreg.CloseKey(aKey)


def get_registry_keys(root_key, path):
    """Get registry keys. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param path: key path
    :return: all keys under given key path
    :type root_key: str
    :type path: str
    :rtype: list
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    key_list = [winreg.EnumKey(aKey, i) for i in range(winreg.QueryInfoKey(aKey)[0])] if aKey else None
    winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)
    return key_list


def set_registry_binary(root_key, key, value, data):
    """Set value data  pair on key. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param key: key path
    :param value: value name
    :param data: string to set
    :type root_key: str
    :type key: str
    :type value: str
    :type data: byte
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, key, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    winreg.SetValueEx(aKey, value, 0, winreg.REG_BINARY, data)
    winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)


def set_dword(root_key, key, value, dword_data):
    """Set DWORD value/name on registry. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param key: key path
    :param value: value name
    :param dword_data: dword_data
    :type root_key: str
    :type key: str
    :type value: str
    :type dword_data: int
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, key, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    def to_unsigned_int(n, radix=32):
        """
        If n is a negative int, convert it to unsigned int
        For example: if n=-1, the function returns 4294967295
        """
        return n if n >= 0 else ((1 << radix) + n)

    winreg.SetValueEx(aKey, value, 0, winreg.REG_DWORD, to_unsigned_int(int(dword_data)))
    winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)


def delete_registry_tree(root_key, path):
    """Deletes a subkeys and any child keys. keyword level should call the function with HandlingExceptions.

    :param root_key: root HKEY
    :param path: key path
    :type root_key: str
    :type path: str
    """
    aReg = winreg.ConnectRegistry(None, reg_mapper()[root_key])
    aKey = winreg.OpenKey(aReg, path, 0, (get_os_registry_architecture() + winreg.KEY_ALL_ACCESS))

    if aKey:
        subKeys = get_registry_keys(root_key, path)
        if subKeys is not None:
            for sub in subKeys:
                delete_registry_tree(root_key, '{path}\\{sub}'.format(path=path, sub=sub))
        delete_registry_key(root_key, path)
        winreg.CloseKey(aKey)
    winreg.CloseKey(aReg)


def get_mguid():
    """
    get the machine's mguid from the registry
    :return: mguid, string
    """
    mguid = get_registry_value('HKEY_LOCAL_MACHINE', r"Software\Microsoft\Cryptography", 'MachineGuid')
    logger.debug('mguid is: {}'.format(mguid))
    return mguid


def set_mguid(new_mguid):
    """
    get the machine's mguid from the registry
    """
    set_registry_value('HKEY_LOCAL_MACHINE', r"Software\Microsoft\Cryptography", 'MachineGuid', new_mguid)


def disable_lua(raise_on_failure=True):
    """Disables LUA in the Windows registry.
       LUA/UAC - is User Account Control in Microsoft Windows that gives you a system-level privilege control mechanism
       """
    try:
        root_key = "HKEY_LOCAL_MACHINE"
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

        # Modify the existing value
        set_dword(root_key, path, "EnableLUA", 0)
        logger.info("EnableLUA value updated to 0")

    except Exception as e:
        logger.error(f"Error disabling LUA (suppressed): {e}")
        if raise_on_failure:
            raise
        else:
            return False


def enable_lua(raise_on_failure=True):
    """Enable LUA in the Windows registry.
       LUA/UAC - is User Account Control in Microsoft Windows that gives you a system-level privilege control mechanism
    """
    try:
        root_key = "HKEY_LOCAL_MACHINE"
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

        # Modify the existing value
        set_dword(root_key, path, "EnableLUA", 1)
        logger.info("EnableLUA value updated to 1")

    except Exception as e:
        logger.error(f"Error enabling LUA (suppressed): {e}")
        if raise_on_failure:
            raise
        else:
            return False
