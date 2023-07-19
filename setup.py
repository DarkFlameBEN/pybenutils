from setuptools import setup, find_packages
from codecs import open
import platform
import pybenutils
import os


scriptFolder = os.path.dirname(os.path.realpath(__file__))
os.chdir(scriptFolder)

with open(r'requirements.txt') as req_file:
    requirements_list = [line.strip() for line in req_file.readlines() if
                         not line.strip().startswith('#') and not line.strip().startswith('-') and line.strip()]

final_requirements_list = list(requirements_list)

# XP workaround for psutil
if platform.release() == 'XP':
    psutil_index = None
    for index, req in enumerate(final_requirements_list):
        if req.startswith('psutil'):
            psutil_index = index
            break
    if psutil_index:
        final_requirements_list[psutil_index] = 'psutil==3.4.2'

with open('README.md', 'r') as readme_file:
    readme_content = readme_file.read()


setup(
    name='pybenutils',
    version=pybenutils.__version__,
    description='PyBEN Utilities repository',
    long_description=readme_content,
    long_description_content_type='text/markdown',
    url='https://github.com/DarkFlameBEN/pybenutils.git',
    author=pybenutils.__author__,
    author_email=pybenutils.__author_email__,
    license='MIT License',
    classifiers=[
        # "Development Status :: 1 - Planning",
        # "Development Status :: 2 - Pre-Alpha",
        "Development Status :: 3 - Alpha",
        # "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
        # "Development Status :: 6 - Mature",
        # "Development Status :: 7 - Inactive",
        "Intended Audience :: Developers",
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        # 'Programming Language :: Python :: 2.7',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    install_requires=final_requirements_list,
    include_package_data=True,
    packages=find_packages(exclude=['tests']),
    python_requires='>3'
)
