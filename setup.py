from setuptools import setup
from codecs import open
import platform


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


setup(
    name='pybenutils',
    version='0.0.1.2',
    description='PyBEN Utilities repo',
    long_description='PyBEN Utilities repo',
    url='https://github.com/DarkFlameBEN/pybenutils.git',
    author='Ben Moskovitch',
    author_email='"Ben Moskovitch" <darkflameben@gmail.com>',
    license='MIT License',
    classifiers=[
        # "Development Status :: 1 - Planning",
        "Development Status :: 2 - Pre-Alpha",
        # "Development Status :: 3 - Alpha",
        # "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
        # "Development Status :: 6 - Mature",
        # "Development Status :: 7 - Inactive",
        "Intended Audience :: Developers",
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        # 'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.7',
    ],
    install_requires=final_requirements_list,
    python_requires='>3'
)
