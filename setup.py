# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import trustee

setup(
    name='trustee',
    version=trustee.__version__,
    description='A simple tool to help verify the identity of cloud resources.',
    author='Oren Shklarsky',
    author_email='orenshk@gmail.com',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'trustee = trustee.dispatch:main'
        ]
    },
    install_requires=[
        'boto3>=1.7,<1.8'
    ]
)