import os
import subprocess
import sys
from subprocess import Popen
from pybenutils.network.download_manager import download_url
from pybenutils.utils_logger.config_logger import get_logger

logger = get_logger()


def update_chrome_browser():
    """Updating Chrome browser to its latest version. Returns True if successful, Raise exception on fail"""
    if sys.platform == 'win32':
        logger.info('Downloading chrome standalone 64 bit version')
        download_url('https://dl.google.com/tag/s/appguid%3D%7B8A69D345-D564-463C-AFF1-A69D9E530F96%7D%26iid%3'
                     'D%7B2FBBE98E-4188-4D38-EB51-8DC406611FB1%7D%26lang%3Den%26browser%3D3%26usagestats%3D0%2'
                     '6appname%3DGoogle%2520Chrome%26needsadmin%3Dprefers%26ap%3Dx64-stable-statsdef_1%26insta'
                     'lldataindex%3Dempty/chrome/install/ChromeStandaloneSetup64.exe')

        process = Popen(f'"{os.path.realpath("ChromeStandaloneSetup64.exe")}" /silent /install', shell=True)
        process.communicate()
        logger.info('Chrome installer finished')
    else:
        download_url('https://dl.google.com/dl/chrome/mac/universal/stable/gcea/googlechrome.dmg')

        cmd = r'hdiutil attach googlechrome.dmg ' \
              r'&& rm -R /Applications/Google Chrome.app ' \
              r'&& cp -pPR "/Volumes/Google Chrome/Google Chrome.app" /Applications/'
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        p.communicate()
    return True
