#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ecs_composex` package."""

from os import path
from os import environ

import pytest
import json
import boto3
import botocore.session
from botocore.stub import Stubber

from troposphere import Template, Parameter

from ecs_composex.common import (
    init_template,
    build_template,
    add_parameters,
    load_composex_file,
    validate_kwargs,
    validate_resource_title,
    validate_input,
)
from ecs_composex.common.aws import get_curated_azs, get_account_id
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.files import FileArtifact
from ecs_composex.vpc import vpc_params
from ecs_composex.common.cfn_tools import import_parameters_into_config_file


@pytest.fixture
def here():
    return path.abspath(path.dirname(__file__))


def test_init_template():
    """
    Test that makes sure we get a new template
    """
    tpl = init_template()
    assert isinstance(tpl, Template)
    tpl = init_template("Override")
    assert tpl.description == "Override"
    add_parameters(tpl, [Parameter("Test", Type="String")])
    assert len(tpl.parameters) == 1
    assert tpl.parameters["Test"].Type == "String"
    add_parameters(tpl, [vpc_params.VPC_ID])
    assert len(tpl.parameters) == 2
    assert tpl.parameters[vpc_params.VPC_ID_T].Type == vpc_params.VPC_TYPE


def test_build_template():
    """
    Testing build template which is a merge of init and add_parameters
    """
    tpl = build_template("Override", [vpc_params.VPC_ID, vpc_params.VPC_MAP_ID])
    assert isinstance(tpl, Template)
    assert isinstance(tpl.parameters[vpc_params.VPC_ID_T], Parameter)
    assert len(tpl.parameters) == 5
    assert tpl.description == "Override"


def test_load_file(here):
    """
    Function to test loading file based on path
    :return:
    """
    output = load_composex_file(f"{here}/all_modules.yml")
    assert isinstance(output, dict)
    with pytest.raises(Exception):
        load_composex_file(f"{here}/app01.yml")


@pytest.fixture
def valid_test_content(here):
    """
    Function to import a YML file for fixture
    :return:
    """
    return load_composex_file(f"{here}/all_modules.yml")


@pytest.fixture
def faulty_test_content(here):
    """
    Function to import a YML file for fixture
    :return:
    """
    return load_composex_file(f"{here}/all_modules.faulty.yml")


@pytest.fixture
def test_cfn_template(here):
    with open(f"{here}/app01.json", "r") as tpl_fd:
        return json.loads(tpl_fd.read())


def test_validate_kwargs(valid_test_content):
    """
    Function to test dict keys validation
    :return:
    """
    required_pass = ["services", "x-rds"]
    required_fail = ["services", "x-dodo"]
    assert validate_kwargs(required_pass, valid_test_content)
    with pytest.raises(KeyError):
        validate_kwargs(required_fail, valid_test_content)


def test_validate_resource_names(valid_test_content, faulty_test_content):
    """
    Function to test
    :param valid_test_content:
    :param faulty_test_content:
    :return:
    """
    assert validate_resource_title("abcd01", "dummy")
    with pytest.raises(ValueError):
        validate_resource_title("abcd-01", "dummy")
    assert validate_input(valid_test_content, "x-rds")
    with pytest.raises(KeyError):
        validate_input(valid_test_content, "x-dodo")
    with pytest.raises(ValueError):
        validate_input(faulty_test_content, "x-rds")


def test_azs():
    session = botocore.session.get_session()
    response = {
        "AvailabilityZones": [{"ZoneName": "eu-west-1a"}, {"ZoneName": "eu-west-1b"}]
    }
    ec2 = session.create_client("ec2")
    stub = Stubber(ec2)
    stub.add_response("describe_availability_zones", response)
    stub.activate()
    azs = get_curated_azs(client=ec2)
    expected_azs = ["eu-west-1a", "eu-west-1b"]
    assert expected_azs == azs
    get_curated_azs(region="us-east-1")


def test_account_id():
    """
    Function to test AccountID
    """
    session = botocore.session.get_session()
    response = {
        "Account": "012345678912",
        "UserId": "ADFTGHJK",
        "Arn": "arn:aws:sts::012345678912:user/toto",
    }
    sts = session.create_client("sts")
    stub = Stubber(sts)
    stub.add_response("get_caller_identity", response)
    stub.activate()
    account_id = get_account_id(client=sts)
    assert account_id == response["Account"]


def test_file_artifact(valid_test_content):
    """
    Testing FileArtifact
    :return:
    """
    with pytest.raises(TypeError):
        # Checks that non Template object raises TypeError
        FileArtifact("test.yml", valid_test_content)
    test_file = FileArtifact("test.yml", content=valid_test_content)
    test_file.define_file_specs()
    test_file.define_body()
    test_file.write()
    assert path.exists(test_file.file_path)


def test_compose_stack(test_cfn_template):
    """
    Tests compose stack
    :return:
    """
    depends_list = ["abcd"]
    depends_str = "123"
    test_depends = ["abcd", "123"]
    template = build_template()
    stack = ComposeXStack("test", stack_template=template)
    stack.add_dependencies(depends_list)
    assert stack.DependsOn == depends_list
    stack.add_dependencies(depends_str)
    assert stack.DependsOn == test_depends
    tpl_file = FileArtifact("test.yml", content=test_cfn_template)
    stack = ComposeXStack("test", template, template_file=tpl_file)
    assert stack.template_file.file_path == tpl_file.file_path


def test_cfn_tools(here):
    """
    Function to test cfn related tools
    """
    params_file = f"{here}/test.params.json"
    config_file = f"{here}/test.config.json"
    expected_config_file = f"{here}/expected.config.json"
    import_parameters_into_config_file(params_file, config_file)
    with open(expected_config_file, "r") as expected_fd:
        expected = json.loads(expected_fd.read())
    with open(config_file, "r") as config_fd:
        config = json.loads(config_fd.read())
    assert expected == config
