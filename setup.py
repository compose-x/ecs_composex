#!/usr/bin/env python
# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The setup script for ECS ComposeX"""

import os
import re
from setuptools import setup, find_packages

DIR_HERE = os.path.abspath(os.path.dirname(__file__))
# REMOVE UNSUPPORTED RST syntax
REF_REGX = re.compile(r"(\:ref\:)")

with open(f"{DIR_HERE}/README.rst", encoding="utf-8") as readme_file:
    readme = readme_file.read()
    readme = REF_REGX.sub("", readme)

with open(f"{DIR_HERE}/HISTORY.rst", encoding="utf-8") as history_file:
    history = history_file.read()

requirements = []
with open(f"{DIR_HERE}/requirements.txt", "r") as req_fd:
    for line in req_fd:
        requirements.append(line.strip())

test_requirements = []
with open(f"{DIR_HERE}/requirements_dev.txt", "r") as req_fd:
    for line in req_fd:
        test_requirements.append(line.strip())

setup_requirements = []

setup(
    author="John Preston",
    author_email="john@lambda-my-aws.io",
    python_requires=">=3.6.*",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Implement for AWS ECS and Docker Compose what SAM is to Serverless for AWS Lambda",
    entry_points={
        "console_scripts": [
            "composex=ecs_composex.cli:main",
            "ecs-composex=ecs_composex.cli:main",
            "ecs_composex=ecs_composex.cli:main",
        ]
    },
    install_requires=requirements,
    license="GPLv3+",
    long_description=readme,
    long_description_content_type="text/x-rst",
    include_package_data=True,
    keywords="ecs_composex",
    name="ecs_composex",
    packages=find_packages(include=["ecs_composex", "ecs_composex.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/lambda-my-aws/ecs_composex",
    version="0.8.1",
    zip_safe=False,
)
