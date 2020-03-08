#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import pytest
import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from ecs_composex.sqs import create_sqs_template
from ecs_composex.sqs.sqs_perms import generate_sqs_permissions

try:
    BUCKET = os.environ['KNOWN_BUCKET']
except KeyError:
    BUCKET = 'lambda-dev-eu-west-1'


CONFIG = {
    'BucketName': BUCKET,
    'EnvName': 'abcd',
}

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def content_sqs():
    """
    Opens the file and passes the content around
    """
    with open(f"{HERE}/sqs.yml", 'r') as fd:
        content = yaml.load(fd.read(), Loader=Loader)
    return content

@pytest.fixture
def args():
    return {
        'BucketName': BUCKET,
        'Debug': True
    }


@pytest.fixture
def parser_args():
    return({
        'ComposeXFile': f"{HERE}/services_with_queues.yml",
        'BucketName': BUCKET,
        'OutputFile': '/tmp/sqs.yml'
    })

def test_generate_policies(args):
    """
    Function to test generation of a queue policies
    """
    policies = generate_sqs_permissions(
        'QueueA', {
            'Services': [
                {
                    'name': 'App01',
                    'access': 'RWMessages'
                }
            ]
        },
        **args
    )
    assert len(policies.keys()) == 3


def simulate_cli_input(parser_args):
    """
    Tests
    """
    create_sqs_template(**parser_args)
