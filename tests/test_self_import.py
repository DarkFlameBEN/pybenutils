from unittest import TestCase
from pybenutils.utils_logger.config_logger import get_logger


class TestSuite(TestCase):
    def test_successful_import(self):
        logger = get_logger()
        logger.info('Logger import working correctly')
        logger.debug(logger.name)
        self.assertTrue(True)
