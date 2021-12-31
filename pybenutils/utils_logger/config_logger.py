import os
import sys
import logging
import inspect
import logging.config
from collections import defaultdict
from logging.handlers import RotatingFileHandler

INITIALIZED = defaultdict(bool)


def set_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    fh = RotatingFileHandler('{}.log'.format(logger_name), 'w+', encoding='utf-8')
    formatter = logging.Formatter(
        '[%(asctime)s] | %(module)-20s | %(funcName)-20s | %(levelname)-7s : %(message)s')
    fh.setFormatter(formatter)

    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    eh = logging.StreamHandler(stream=sys.stderr)
    eh.setLevel(logging.ERROR)
    eh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

    INITIALIZED[logger_name] = True

    return logger


def get_logger(logger_name='main_logger'):
    """Returns a logger object with a given title

    :param logger_name: If empty the logger name will be based on the calling module
    :return: Logger object
    """
    if not logger_name:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        logger_name = os.path.basename(module.__file__)
    return logging.getLogger(logger_name) if INITIALIZED[logger_name] else set_logger(logger_name)
