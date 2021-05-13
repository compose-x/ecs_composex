#!/usr/bin/env python
#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

"""The setup script for ECS ComposeX"""

import os
import re
from setuptools import setup, find_packages

DIR_HERE = os.path.abspath(os.path.dirname(__file__))
# REMOVE UNSUPPORTED RST syntax
REF_REGX = re.compile(r"(\:ref\:)")

try:
    with open(f"{DIR_HERE}/README.rst", encoding="utf-8") as readme_file:
        readme = readme_file.read()
        readme = REF_REGX.sub("", readme)
except FileNotFoundError:
    readme = "ECS ComposeX"

try:
    with open(f"{DIR_HERE}/HISTORY.rst", encoding="utf-8") as history_file:
        history = history_file.read()
except FileNotFoundError:
    history = "Latest packaged version."

requirements = []
with open(f"{DIR_HERE}/requirements.txt", "r") as req_fd:
    for line in req_fd:
        requirements.append(line.strip())

test_requirements = []
try:
    with open(f"{DIR_HERE}/requirements_dev.txt", "r") as req_fd:
        for line in req_fd:
            test_requirements.append(line.strip())
except FileNotFoundError:
    print("Failed to load dev requirements. Skipping")

setup_requirements = []

setup(
    author="John Preston",
    author_email="john@compose-x.io",
    python_requires=">=3.6.*",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Implement for AWS ECS and Docker Compose what SAM is to Serverless for AWS Lambda",
    entry_points={
        "console_scripts": [
            "ecs-compose-x=ecs_composex.cli:main",
            "ecs_compose_x=ecs_composex.cli:main",
        ]
    },
    install_requires=requirements,
    license="MPL-2.0",
    long_description=readme,
    long_description_content_type="text/x-rst",
    include_package_data=True,
    keywords="ecs_composex aws cloudformation iac docker compose",
    name="ecs_composex",
    packages=find_packages(include=["ecs_composex", "ecs_composex.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/compose-x/ecs_composex",
    version="0.15.0",
    zip_safe=False,
)
