from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


def compare_nested_objects(obj1, obj2):
    """Compare two nested objects and returns the number of mismatched nodes between them

    :param obj1: First object
    :param obj2: Second object
    :return: Number of mismatched nodes between the objects
    """
    total_of_mismatched_found = 0
    if type(obj1) != type(obj2):
        logger.info('obj types do not match. obj1:{}, type:{} do not match obj2:{}, type:{}'.format(
            obj1, type(obj1), obj2, type(obj2)))
        return 1
    if type(obj1) == str:
        if obj1 != obj2:
            logger.info('string "{}" do not match "{}"'.format(obj1, obj2))
            return 1
        else:
            return 0
    if len(obj2) > len(obj1):
        temp_obj = obj1
        obj1 = obj2
        obj2 = temp_obj
    if type(obj1) == list:
        if not obj1:  # checks if the list is empty
            if not obj2:  # checks if the list is empty
                return 0
            else:
                logger.info('List "{}" is empty on the second list'.format(obj2))
                return 1
        if not obj2:  # checks if the list is empty
            logger.info('List "{}" is empty on the second list'.format(obj1))
            return 1
        mismatched_counter_in_list = 0
        for obj_in_list_a, obj_in_list_b in zip(obj1, obj2):
            mismatched_counter_in_list += compare_nested_objects(obj_in_list_a, obj_in_list_b)
        return mismatched_counter_in_list
    if type(obj1) == dict:
        if not obj1:  # checks if the dict is empty
            if not obj2:
                return 0
            else:
                logger.info('Dict {} is empty on the second dict'.format(obj2))
                return 1
        for obj1_key, value_of_obj1_key in obj1.items():
            if obj1_key not in obj2:
                logger.info('Dict key "{}" appears on one obj and missing from the other'.format(obj1_key))
                total_of_mismatched_found += 1
            else:
                if value_of_obj1_key != obj2[obj1_key]:
                    total_of_mismatched_found += compare_nested_objects(obj1[obj1_key], obj2[obj1_key])
    return total_of_mismatched_found
