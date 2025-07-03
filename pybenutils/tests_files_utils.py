import inspect
import os
from importlib import import_module
from pprint import pprint
from typing import Dict, List


def get_qase_id(test_function):
    """Extract Qase ID from a test function if it has @qase.id decorator."""
    if hasattr(test_function, "pytestmark"):
        marks = test_function.pytestmark
        for mark in marks:
            if getattr(mark, "name", None) == 'qase_id':
                return mark.kwargs.get('id')
    return None


def extract_tests_from_file(full_file_path, import_path):
    """Extract test case details from a test file, including Qase IDs."""
    try:
        module = import_module(import_path)
    except ModuleNotFoundError:
        print(f"Module not found: {import_path}")
        return None
    except Exception as e:
        print(f"Error importing {import_path}: {e}")
        return None

    file_index = {
        "Suite Name": os.path.basename(full_file_path).replace("_", " ").rsplit(".", 1)[0],
        "Description": inspect.getdoc(module) or "",
        "Test Cases": []
    }

    for test_name, test_function in inspect.getmembers(module, inspect.isfunction):
        if test_name.startswith("test_"):
            test_desc = inspect.getdoc(test_function) or ""
            qase_id = get_qase_id(test_function)

            file_index["Test Cases"].append({
                "Qase ID": qase_id if qase_id else "",
                "UID": test_name.split("test_", 1)[-1].split("_", 1)[0],
                "Name": test_name,
                "Description": test_desc
            })

    return file_index


def get_pytest_files_index(search_dir = '') -> List[Dict]:
    """Returns an object of all the test files"""
    if not search_dir:
        search_dir = os.getcwd()
    base_dir = os.getcwd()
    if os.path.basename(base_dir) == 'docs':
        base_dir = os.path.dirname(base_dir)

    full_index = []
    for root, _, files in os.walk(os.path.relpath(search_dir)):
        for file_name in files:
            if file_name.startswith("test_") and file_name.endswith(".py") and not root.startswith("__"):
                full_path = os.path.join(root, file_name)
                partial_path = os.path.relpath(full_path, base_dir).replace(os.path.sep, ".").rsplit(".", 1)[0]

                file_index = extract_tests_from_file(full_path, partial_path)
                if file_index:
                    full_index.append(file_index)
    return full_index


def get_uuid_index(search_dir = '', validate_integrity=False):
    """Returns an object of all the test cases index by uuid

    :param search_dir: Root directory to search for test cases
    :param validate_integrity: Check for duplicates uuid in test cases and non-numeric uuid
    :return: Dictionary of test cases index by uuid
    """
    files = get_pytest_files_index(search_dir=search_dir)
    index_by_uuid = {}
    warnings = []
    for file_dict in files:
        for test_case in file_dict.get("Test Cases", []):
            if test_case["UID"]:
                if validate_integrity:
                    if index_by_uuid.get(test_case["UID"]):
                        warnings.append(f'Duplicate test case UID: {test_case["UID"]}')
                    if not test_case["UID"].isnumeric():
                        warnings.append(f'Test case UID is not a number: {test_case}')
                index_by_uuid[test_case["UID"]] = test_case

    if validate_integrity:
        pprint(warnings)
        assert not warnings, 'Found issues while building the index'
    return index_by_uuid
