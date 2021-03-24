﻿#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from os import path
import pytest
import placebo
import boto3
from botocore.exceptions import ClientError
from botocore.errorfactory import ClientExceptionsFactory
from troposphere import Ref
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.dns import DnsSettings
from ecs_composex.common import load_composex_file, build_template
from ecs_composex.dns.dns_records import Record


@pytest.fixture
def content():
    here = path.abspath(path.dirname(__file__))
    return load_composex_file(f"{here}/../../use-cases/blog.yml")


@pytest.fixture
def zone_create():
    return {
        "x-dns": {
            "PrivateNamespace": {"Name": "mycluster.lan"},
            "PublicNamespace": {"Name": "lambda-my-aws.io"},
        }
    }


@pytest.fixture
def zone_lookup():
    return {
        "x-dns": {
            "PrivateNamespace": {"Name": "mycluster.lan", "Lookup": "ns-aieijfieojf"},
            "PublicNamespace": {
                "Name": "lambda-my-aws.io",
                "Lookup": "ns-abaiejfiefjio",
            },
        }
    }


def create_settings(updated_content, case_path):
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path="/tmp/")
    try:
        pill.playback()
    except OSError:
        pill.record()
    settings = ComposeXSettings(
        content=updated_content,
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.input_file_arg: path.abspath(
                f"{here}/../../use-cases/blog.yml"
            ),
            ComposeXSettings.format_arg: "yaml",
        },
    )
    return settings


def test_zone_create(content, zone_create):
    """
    Tests zone lookup
    :return:
    """
    print(content)
    updated_content = content.copy()
    updated_content.update(zone_create)
    settings = create_settings(updated_content, "x_dns")
    root_stack = ComposeXStack("root", build_template())
    DnsSettings(root_stack, settings, Ref("VpcId"))


def test_zone_lookup(content, zone_lookup):
    """
    Tests zone lookup
    :return:
    """
    updated_content = content.copy()
    updated_content.update(zone_lookup)
    settings = create_settings(updated_content, "x_dns")
    root_stack = ComposeXStack("root", build_template())
    try:
        DnsSettings(root_stack, settings, Ref("VpcId"))
    except Exception:
        pass


def test_valid_records():
    """
    Function to test valid records
    """
    r = Record({"Properties": {}, "Names": ["google.com", "test.net", "amazonaws.com"]})


def test_invalid_records():
    """
    Function to test valid records
    """
    with pytest.raises(TypeError):
        Record(
            {
                "Properties": {},
                "Names": ["google.com", "test.net", "amazonaws.com", ["something.net"]],
            }
        )
    with pytest.raises(NameError):
        Record(
            {
                "Properties": {},
                "Names": [
                    "google.com",
                    "test.net",
                    "amazonaws.com",
                    "invalid_domain.net",
                ],
            }
        )
