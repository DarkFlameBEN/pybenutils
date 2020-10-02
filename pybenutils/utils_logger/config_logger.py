import logging
import logging.config
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import sys
import traceback
INITIALIZED = defaultdict(bool)


def set_logger(logger_name='main_logger'):
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
    # logger.addHandler(eh)
    logger.addHandler(fh)

    INITIALIZED[logger_name] = True

    # def exception_handler(exctype, value, tb):
    #     logger.exception('{type}\n\tEXCEPTION: {value}\n\tEXCEPTION: {tb}'.format(
    #         type=str(exctype), value=str(value), tb=traceback.extract_tb(tb)))
    # sys.excepthook = exception_handler
    return logger


def get_logger(logger_name='main_logger'):
    return logging.getLogger(logger_name) if INITIALIZED[logger_name] else set_logger(logger_name)
