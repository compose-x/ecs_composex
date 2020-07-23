#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os import path
import pytest
import placebo
import boto3
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common import load_composex_file
from ecs_composex.vpc.vpc_params import VPC_ID_T


@pytest.fixture
def content():
    here = path.abspath(path.dirname(__file__))
    return load_composex_file(f"{here}/../use-cases/blog.yml")


@pytest.fixture
def x_vpc_arn():
    return {
        "VpcId": "arn:aws:ec2:eu-west-1:012345678912:vpc/vpc-08144c139f0a4a671",
        "AppSubnets": "subnet-0b0d3c7251ad0af8c,subnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef17",
            "subnet-0d49c1240b794118d",
            "subnet-04270d634ef29f545",
        ],
        "PublicSubnets": {"tags": [{"vpc::usage": "public"}]},
    }


@pytest.fixture
def invalid_x_vpc_arn():
    return {
        "VpcId": "arn:aws:ec2:eu-west-1:01234678912:vpc-08144c139f0a4a671",
        "AppSubnets": "subnet-0b0d3c7251ad0af8c,subnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef17",
            "subnet-0d49c1240b794118d",
            "subnet-04270d634ef29f545",
        ],
        "PublicSubnets": {"tags": [{"vpc::usage": "public"}]},
    }


@pytest.fixture
def x_vpc_id():
    return {
        "VpcId": "vpc-08144c139f0a4a671",
        "AppSubnets": "subnet-0b0d3c7251ad0af8c,subnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef17",
            "subnet-0d49c1240b794118d",
            "subnet-04270d634ef29f545",
        ],
        "PublicSubnets": {"tags": [{"vpc::usage": "public"}]},
    }


@pytest.fixture
def invalid_x_vpc_id():
    return {
        "VpcId": "vpc-08144c139fABCD",
        "AppSubnets": "subnet-0b0d3c7251ad0af8c,subnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef17",
            "subnet-0d49c1240b794118d",
            "subnet-04270d634ef29f545",
        ],
        "PublicSubnets": {"tags": [{"vpc::usage": "public"}]},
    }


@pytest.fixture
def x_vpc_tags():
    return {
        "VpcId": {"tags": [{"Name": "vpcwork"}]},
        "AppSubnets": "subnet-0b0d3c7251ad0af8c,subnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef17",
            "subnet-0d49c1240b794118d",
            "subnet-04270d634ef29f545",
        ],
        "PublicSubnets": {"tags": [{"vpc::usage": "public"}]},
    }


@pytest.fixture
def invalid_x_subnets_ids():
    return {
        "VpcId": {"tags": [{"Name": "vpcwork"}]},
        "AppSubnets": "subnet-0b0d3c7251ad0af8csubnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef17",
            "subnet-0d49c1240b794118d",
            "subnet-04270d634ef29f545",
        ],
        "PublicSubnets": {"tags": [{"usage": "public"}]},
    }


@pytest.fixture
def invalid_x_subnets_ids_list():
    return {
        "VpcId": {"tags": [{"Name": "vpcwork"}]},
        "AppSubnets": "subnet-0b0d3c7251ad0af8c,subnet-0b0e0f4f2ac3fa46d,subnet-06d3130b79d277b1b",
        "StorageSubnets": [
            "subnet-004e206426fdaef1A",
            "subnet-0d49c1240b794118A",
            "subnet-04270d634ef29f54A",
        ],
        "PublicSubnets": {"tags": [{"usage": "public"}]},
    }


def create_settings(updated_content, case_path):
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/{case_path}")
    pill.playback()
    settings = ComposeXSettings(
        content=updated_content,
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.input_file_arg: path.abspath(
                f"{here}/../features/use-cases/vpc/vpc_from_tags.yml"
            ),
            ComposeXSettings.no_upload_arg: True,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    return settings


def test_vpc_import_from_tags(content, x_vpc_tags):
    content.update({"x-vpc": {"Lookup": x_vpc_tags}})
    settings = create_settings(content, "x_vpc")
    assert hasattr(settings, VPC_ID_T) and getattr(settings, VPC_ID_T) is not None
    with pytest.raises(ValueError):
        """Validates double VPC raises an error"""
        settings.lookup_x_vpc_settings(x_vpc_tags)


def test_vpc_import_from_arn(content, x_vpc_arn):
    content.update({"x-vpc": {"Lookup": x_vpc_arn}})
    settings = create_settings(content, "x_vpc")
    assert hasattr(settings, VPC_ID_T) and getattr(settings, VPC_ID_T) is not None


def test_vpc_import_from_id(content, x_vpc_id):
    content.update({"x-vpc": {"Lookup": x_vpc_id}})
    settings = create_settings(content, "x_vpc")
    assert hasattr(settings, VPC_ID_T) and getattr(settings, VPC_ID_T) is not None


def test_negative_testing_vpc(content, invalid_x_vpc_id, invalid_x_vpc_arn):
    content.update({"x-vpc": {"Lookup": invalid_x_vpc_id}})
    with pytest.raises(ValueError):
        settings = create_settings(content, "x_vpc")
    content.update({"x-vpc": {"Lookup": invalid_x_vpc_arn}})
    with pytest.raises(ValueError):
        settings = create_settings(content, "x_vpc")


def test_negative_testing_subnets(
    content, invalid_x_subnets_ids, invalid_x_subnets_ids_list
):
    content.update({"x-vpc": {"Lookup": invalid_x_subnets_ids}})
    with pytest.raises(ValueError):
        settings = create_settings(content, "x_vpc")
    content.update({"x-vpc": {"Lookup": invalid_x_subnets_ids_list}})
    with pytest.raises(ValueError):
        settings = create_settings(content, "x_vpc")

    with pytest.raises(ValueError):
        """On 4th call, no subnets are returned"""
        settings = create_settings(content, "x_vpc")
        settings = create_settings(content, "x_vpc")
        settings = create_settings(content, "x_vpc")
        settings = create_settings(content, "x_vpc")
