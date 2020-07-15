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

from behave import given, then

from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import render_final_template
from ecs_composex.ecs_composex import generate_full_template


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
    context.settings = ComposeXSettings(
        profile_name=getattr(context, "profile_name")
        if hasattr(context, "profile_name")
        else None,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.input_file_arg: cases_path,
            ComposeXSettings.no_upload_arg: True,
            ComposeXSettings.format_arg: "yaml",
        },
    )


@given("I want to create a VPC")
def step_impl(context):
    context.settings.create_vpc = True
    context.settings.vpc_cidr = ComposeXSettings.default_vpc_cidr


@given("I want to create a Cluster")
def step_impl(context):
    context.settings.create_cluster = True


@then("I render all files to verify execution")
def set_impl(context):
    render_final_template(generate_full_template(context.settings), context.settings)


@given("I want to use aws profile {profile_name}")
def step_impl(context, profile_name):
    """
    Function to change the session to a specific one.
    """
    context.session_name = profile_name


@given("I want to upload files to S3 bucket {bucket_name}")
def step_impl(context, bucket_name):
    context.settings.upload = True
    context.settings.no_upload = False
    context.settings.bucket_name = bucket_name
