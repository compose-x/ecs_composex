#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, Extension, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'troposphere==2.6.0',
    'boto3==1.12.9'
]

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest>=3', ]

setup(
    author="John Mille",
    author_email='john@lambda-my-aws.io',
    python_requires='!=2.*, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    description="Package that generates CFN templates based on a Docker Compose file to generate ECS Cluster,"
                "ECS Services and Extra resources such as SQS Queues, SNS Topics etc. that can be accessed via IAM",
    entry_points={
        'console_scripts': [
            'ecs_composex=ecs_composex.cli:main',
            'ecs_composex-vpc=ecs_composex.vpc.cli:main',
            'ecs_composex-sqs=ecs_composex.sqs.cli:main'
        ]
    },
    install_requires=requirements,
    license="BSD license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='ecs_composex',
    name='ecs_composex',
    packages=find_packages(include=['ecs_composex', 'ecs_composex.*']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/lambda-my-aws/ecs_composex',
    version='0.1.0',
    zip_safe=False
)
