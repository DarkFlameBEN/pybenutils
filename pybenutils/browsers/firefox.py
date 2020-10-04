import sys
import platform
import subprocess
from pybenutils.network.download_manager import download_url
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


def update_firefox_browser():
    """Updating Firefox browser to it's latest version"""
    if sys.platform == 'win32':
        build_source = 'http://download.mozilla.org/?product=firefox-latest&os=win&lang=en-US'
        ff_installer = download_url(build_source, 'firefox_setup.exe')
        p = subprocess.Popen(f'{ff_installer} -ms', shell=True)
        p.communicate()

    elif platform.system() == 'darwin':
        # build_source = 'http://download.mozilla.org/?product=firefox-latest&os=osx&lang=en-US'
        logger.error('WARNING: darwin OS is not supported at this time')
    else:
        subprocess.Popen('sudo apt-get update', shell=True)
        subprocess.Popen('sudo apt-get install firefox', shell=True)
