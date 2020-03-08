#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ecs_composex` package."""

import os
import yaml
import pytest
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from ecs_composex.ecs_composex import generate_x_resource_configs

try:
    BUCKET = os.environ['KNOWN_BUCKET']
except KeyError:
    BUCKET = 'ecs-composex-dev'

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def content():
    """
    Opens the file and passes the content around
    """
    with open(f"{HERE}/services_with_queues.yml", 'r') as fd:
        content = yaml.load(fd.read(), Loader=Loader)
    return content


@pytest.fixture
def args():
    return {
        'BucketName': BUCKET,
        'EnvName': 'abcd',
        'Debug': True
    }


def test_x_resource_permissions(content, args):
    """
    Test generating the permissions for all x- resources
    """
    permissions = generate_x_resource_configs(content, **args)
    assert 'x-sqs' in permissions.keys()
