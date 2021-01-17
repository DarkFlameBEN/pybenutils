import os
import time
import requests
from urllib.parse import urlparse
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


def download_url(url: str, file_path='', attempts=2, raise_failure=True, verify_ssl=True):
    """Downloads a URL content into a file (with large file support by streaming)

    :param url: URL to download_url
    :param file_path: Local file name to contain the data downloaded
    :param attempts: Number of attempts
    :param raise_failure: Raise Exception on failure
    :param verify_ssl: Verify the domain ssl
    :return: New file path. Empty string if the download_url failed
    """
    if not file_path:
        file_path = os.path.realpath(os.path.basename(url))
    logger.info(f'Downloading {url} content to {file_path}')
    url_sections = urlparse(url)
    if not url_sections.scheme:
        logger.debug('The given url is missing a scheme. Adding http scheme')
        url = f'http://{url}'
        logger.debug(f'New url: {url}')
    last_exception = None
    for attempt in range(1, attempts+1):
        try:
            if attempt > 1:
                time.sleep(10)  # 10 seconds wait time between downloads
            with requests.get(url, stream=True, verify=verify_ssl) as response:
                logger.debug(f'Response status code: {response.status_code}')
                response.raise_for_status()
                with open(file_path, 'wb') as out_file:
                    for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        out_file.write(chunk)
                logger.info('Download finished successfully')
                return file_path
        except Exception as ex:
            logger.error(f'Attempt #{attempt} failed with error: {ex}')
            last_exception = ex
    if raise_failure:
        raise last_exception
    return ''
