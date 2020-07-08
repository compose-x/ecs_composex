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

from boto3 import session
from os import path
from behave import given, when, then
from pytest import raises


from ecs_composex.common import load_composex_file
from ecs_composex.common.ecs_composex import XFILE_DEST


def here():
    return path.abspath(path.dirname(__file__))


@given("I use {file_path} as my docker-compose file")
def step_impl(context, file_path):
    """
    Function to import the Docker file from use-cases.

    :param context:
    :param str file_path:
    :return:
    """
    cases_path = path.abspath(f"{here()}/../../{file_path}")
    if not hasattr(context, "kwargs"):
        context.kwargs = {}
    if not "AwsRegion" in context.kwargs.keys():
        context.kwargs["AwsRegion"] = session.Session().region_name
        context.kwargs["NoUpload"] = True
        context.kwargs["BucketName"] = "abcd"
        context.kwargs["VpcCidr"] = "172.23.0.0/24"
        context.kwargs[XFILE_DEST] = cases_path
    context.compose_content = load_composex_file(cases_path)


@given("I want to create a VPC")
def step_impl(context):
    if not hasattr(context, "kwargs"):
        context.kwargs = {}
    context.kwargs.update({"CreateVpc": True})


@given("I want to create a Cluster")
def step_impl(context):
    if not hasattr(context, "kwargs"):
        context.kwargs = {}
    context.kwargs.update({"CreateCluster": True})
