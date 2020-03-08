# -*- coding: utf-8 -*-
#!/usr/bin/env python

import os
import yaml
import pytest
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from ecs_composex.common import build_template
from ecs_composex.ecs.ecs_iam import (
    add_service_roles,
    assign_x_resources_to_service
)

try:
    BUCKET = os.environ['KNOWN_BUCKET']
except KeyError:
    BUCKET = 'lambda-dev-eu-west-1'


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
def config():
    """
    Config object
    """
    return {
        'BucketName': BUCKET,
        'EnvName': 'abcd',
        'Debug': True
    }


def test_ecs_roles(config):
    """
    Tests the creation of service roles
    """
    tmp_tpl = build_template('Tmp template')
    add_service_roles(tmp_tpl)


def test_ecs_roles_permissions(content, config):
    """
    Function to test
    """
    tmp_tpl = build_template('TMP Template')
    add_service_roles(tmp_tpl)
    assign_x_resources_to_service(content, 'app01', tmp_tpl, **config)
