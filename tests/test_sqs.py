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

from os import path, environ
import pytest


@pytest.fixture
def bucket_name():
    try:
        bucket = environ["KNOWN_bucket"]
    except KeyError:
        bucket = "lambda-dev-eu-west-1"
    return bucket


@pytest.fixture
def here():
    return path.abspath(path.dirname(__file__))


@pytest.fixture
def content_sqs(here):
    """
    Opens the file and passes the content around
    """
    with open(f"{here}/sqs.yml", "r") as fd:
        content = yaml.load(fd.read(), Loader=Loader)
    return content


@pytest.fixture
def args(bucket_name):
    return {"BucketName": bucket_name, "Debug": True}


@pytest.fixture
def parser_args(here, bucket_name):
    return {
        "ComposeXFile": f"{here}/services_with_queues.yml",
        "BucketName": bucket_name,
        "OutputFile": "/tmp/sqs.yml",
    }


def test_generate_policies(args):
    """
    Function to test generation of a queue policies
    """
    policies = generate_sqs_permissions(
        "QueueA", {"Services": [{"name": "App01", "access": "RWMessages"}]}, **args
    )
    assert len(policies.keys()) == 3


def simulate_cli_input(parser_args):
    """
    Tests
    """
    create_sqs_template(**parser_args)
