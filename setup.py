#!/usr/bin/env python

from setuptools import setup, find_packages

def readme():
    with open('README.rst') as file:
        return file.read()

setup(name='pyUC',
      version='1.1.0',
      description='USRP Client for DVSwitch',
      long_description='A GUI client to access the DVSwitch digital ham software suite',
      classifiers=[
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)'
          'Programming Language :: Python :: 3'
          'Intended Audience :: Ham Radio Operators'
          'Natural Language :: English'
          'Operating System :: OS Independent'
          'Programming Language :: Python :: Implementation :: CPython'
          'Topic :: Communications :: Ham Radio'
          'Topic :: Software Development :: Libraries :: Python Modules'
          'Topic :: Utilities'
      ],
      keywords='dmr ysf nxdn p25 dstar radio digital mmdvm ham amateur radio',
      author='Michael Zingman, N4IRR',
      author_email='n4irr@amsat.org',
      install_requires=['pyaudio', 'ImageTk', 'BeautifulSoup4', 'pillow', 'requests'],
      license='GPLv3',
      url='https://github.com/DVSwitch/USRP_Client',
      packages=['pyUC'],
      #packages=find_packages()
     )

     # apt-get install portaudio19-dev python3-pil python3-pil.imagetk
