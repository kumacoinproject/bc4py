#!/user/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os

try:
    with open('README.md') as f:
        readme = f.read()
except IOError:
    readme = ''


# version
here = os.path.dirname(os.path.abspath(__file__))
init_path = os.path.join(here, 'bc4py', '__init__.py')
version = next((line.split('=')[1].strip().replace("'", '')
                for line in open(init_path)
                if line.startswith('__version__ = ')),
               '0.0.dev0')

# requirements
with open(os.path.join(here, 'requirements.txt')) as fp:
    install_requires = fp.read().splitlines()
with open(os.path.join(here, 'requirements-c.txt')) as fp:
    install_requires += fp.read().splitlines()

setup(
    name="bc4py",
    version=version,
    url='https://github.com/namuyan/bc4py',
    author='namuyan',
    description='Simple blockchain library for python3.',
    long_description=readme,
    packages=find_packages(),
    install_requires=install_requires,
    include_package_data=True,
    license="MIT Licence",
    classifiers=[
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: MIT License',
    ],
)
