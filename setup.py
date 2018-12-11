#!/user/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os

try:
    with open('README.md') as f:
        readme = f.read()
except IOError:
    readme = ''


def _requires_from_file(filename):
    return open(filename).read().splitlines()


# version
here = os.path.dirname(os.path.abspath(__file__))
init_path = os.path.join(here, 'bc4py', '__init__.py')
version = next((line.split('=')[1].strip().replace("'", '')
                for line in open(init_path)
                if line.startswith('__version__ = ')),
               '0.0.dev0')


setup(
    name="bc4py",
    version=version,
    url='https://github.com/namuyan/bc4py',
    author='namuyan',
    description='Simple blockchain library for python3.',
    long_description=readme,
    packages=find_packages(),
    include_package_data=True,
    license="MIT Licence",
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: MIT License',
    ],
)
