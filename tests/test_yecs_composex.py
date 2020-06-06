#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ecs_composex` package."""

from os import path, environ
import pytest
import boto3

from ecs_composex.common.aws import get_curated_azs
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common import load_composex_file
from ecs_composex.ecs_composex import generate_full_template
from ecs_composex.common.stacks import render_final_template


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
def all_modules(here):
    return load_composex_file(f"{here}/all_modules.yml")


@pytest.fixture
def all_features(here):
    return load_composex_file(f"{here}/all_features.yml")


def test_full(all_modules, bucket_name, here):
    """
    Function to test all modules rfom file
    """
    session = boto3.session.Session()
    args = {
        "BucketName": bucket_name,
        "CreateVpc": True,
        "CreateCluster": True,
        XFILE_DEST: f"{here}/all_modules.yml",
        "AwsAzs": get_curated_azs(session=session),
        "VpcCidr": "172.23.0.0/24",
    }
    template = generate_full_template(all_modules, session=session, **args)


def test_full_features(all_features, bucket_name, here):
    """
    Function to test all features rfom file
    """
    session = boto3.session.Session()
    args = {
        "BucketName": bucket_name,
        "CreateVpc": True,
        "CreateCluster": True,
        XFILE_DEST: f"{here}/all_features.yml",
        "AwsAzs": get_curated_azs(session=session),
        "VpcCidr": "172.23.0.0/24",
        "AddComputeResources": True,
        "NoUpload": True,
    }
    template = generate_full_template(all_features, session=session, **args)
    render_final_template(template[0])
