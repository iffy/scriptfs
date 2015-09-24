#!/usr/bin/env python
# Copyright (c) Matt Haggard
# See LICENSE for details.


from distutils.core import setup

setup(
    name='scriptfs',
    version='0.1.0',
    description='FUSE filesystem with scripts',
    author='Matt Haggard',
    author_email='haggardii@gmail.com',
    url='https://github.com/iffy/scriptfs',
    packages=[
        'scriptfs',
    ],
    install_requires=[
        'PyYaml',
        'fusepy',
    ],
    scripts=[
        'scripts/scriptfs',
    ]
)