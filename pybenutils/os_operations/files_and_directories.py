import os
import re
import stat


def rm_tree(dir_path):
    """Delete directory tree, starting from given path

    :param dir_path: the path to the parent folder
    """
    new_path = os.path.join(os.path.dirname(dir_path), '{}__temp'.format(os.path.basename(dir_path)))
    if os.path.isdir(new_path):
        rm_tree(new_path)
    os.rename(dir_path, new_path)
    for root, dirs, files in os.walk(new_path, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(new_path)


def get_files_in_folder(folder_path, pattern=''):
    """Return a list of files inside a folder and its sub-folders with their full path

    :param folder_path: folder to inspect
    :param pattern: regex pattern to limit the files list
    :return: List of files paths
    """
    files_paths = []
    starting_point = os.path.realpath(folder_path)
    for root, dirs, files in os.walk(starting_point):
        for file_n in files:
            if re.match(pattern, file_n):
                files_paths.append(os.path.join(root, file_n))
    return files_paths
