#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path, environ

import pytest

from ecs_composex.common import load_composex_file
from ecs_composex.rds import XResource
from ecs_composex.rds.rds_template import generate_rds_templates
from ecs_composex.rds.rds_parameter_groups_helper import (
    get_family_from_engine_version,
    get_db_engine_settings,
)


@pytest.fixture
def here():
    return path.abspath(path.dirname(__file__))


@pytest.fixture
def bucket_name():
    try:
        bucket = environ["KNOWN_bucket"]
    except KeyError:
        bucket = "lambda-dev-eu-west-1"
    return bucket


@pytest.fixture
def test_file(here):
    return load_composex_file(f"{here}/rds_only.yml")


def test_generate_rds_template(test_file):
    generate_rds_templates(test_file)


def test_x_resource(test_file, bucket_name):
    template = generate_rds_templates(test_file)
    rds_root = XResource("rds", stack_template=template, **{"BucketName": bucket_name})
    rds_root.template_file.write()
    path.exists(rds_root.template_file.file_path)


def test_get_family_settings():
    engine = "aurora-mysql"
    engine_version = "5.7.12"
    family = get_family_from_engine_version(engine, engine_version)
    assert family == "aurora-mysql5.7"
    settings = get_db_engine_settings(engine, engine_version)
    assert settings["DBParameterGroupFamily"] == "aurora-mysql5.7"
    with pytest.raises(ValueError):
        get_db_engine_settings(engine, "5.6.10a")
    with pytest.raises(ValueError):
        get_db_engine_settings(engine, "5.6.10a", serverless=True)
    get_db_engine_settings("aurora", "5.6.10a", serverless=True)
