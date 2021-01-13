#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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
from pytest import raises

from behave import given, then
import placebo

from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.ecs_composex import generate_full_template
from ecs_composex.common.aws import deploy


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
    cases_path = path.abspath(f"{here()}/../../../{file_path}")
    context.settings = ComposeXSettings(
        profile_name=getattr(context, "profile_name")
        if hasattr(context, "profile_name")
        else None,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.input_file_arg: [cases_path],
            ComposeXSettings.format_arg: "yaml",
        },
    )
    context.settings.set_azs_from_api()
    context.settings.set_bucket_name_from_account_id()


@given(
    "I use {file_path} as my docker-compose file and {override_file} as override file"
)
def step_impl(context, file_path, override_file):
    """
    Function to import the Docker file from use-cases.

    :param context:
    :param str file_path:
    :param str override_file:
    :return:
    """
    cases_path = path.abspath(f"{here()}/../../../{file_path}")
    override_path = path.abspath(f"{here()}/../../../{override_file}")
    context.settings = ComposeXSettings(
        profile_name=getattr(context, "profile_name")
        if hasattr(context, "profile_name")
        else None,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.input_file_arg: [cases_path, override_path],
            ComposeXSettings.format_arg: "yaml",
        },
    )
    context.settings.set_azs_from_api()
    context.settings.set_bucket_name_from_account_id()


@given("I want to create a VPC")
def step_impl(context):
    context.settings.create_vpc = True
    context.settings.vpc_cidr = ComposeXSettings.default_vpc_cidr


@given("I want to create a Cluster")
def step_impl(context):
    context.settings.create_cluster = True


@then("I render all files to verify execution")
def set_impl(context):
    process_stacks(context.root_stack, context.settings)


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


@given("I set I did not want to upload")
def step_impl(context):
    context.settings.upload = False
    context.settings.no_upload = True


@given("I want to deploy to CFN stack named test")
def step_impl(context):
    """
    Function to test the deployment.
    """
    pill = placebo.attach(
        session=context.settings.session, data_path=f"{here()}/cfn_create"
    )
    pill.playback()
    context.stack_id = deploy(context.settings, context.root_stack)


@given("I want to update to CFN stack named test")
def step_impl(context):
    """
    Function to test the deployment.
    """
    pill = placebo.attach(
        session=context.settings.session, data_path=f"{here()}/cfn_update"
    )
    pill.playback()
    context.stack_id = deploy(context.settings, context.root_stack)


@given("I want to update a failed stack named test")
def step_impl(context):
    """
    Function to test the deployment.
    """
    pill = placebo.attach(
        session=context.settings.session, data_path=f"{here()}/cfn_cannot_update"
    )
    pill.playback()
    context.stack_id = deploy(context.settings, context.root_stack)


@then("I should have a stack ID")
def step_impl(context):
    """
    Function to check we got a stack ID
    """
    assert context.stack_id is not None


@then("I should not have a stack ID")
def step_impl(context):
    """
    Function to check we got a stack ID
    """
    assert context.stack_id is None


@given("I render the docker-compose to composex")
def step_impl(context):
    context.root_stack = generate_full_template(context.settings)


@then("I render the docker-compose to composex to validate")
def step_impl(context):
    context.root_stack = generate_full_template(context.settings)


@then("With missing module from file, program quits with code {code:d}")
def step_impl(context, code):
    with raises(SystemExit) as exit_error:
        context.resource_type(context.settings.compose_content, context.settings)
    assert exit_error.value.code == code
