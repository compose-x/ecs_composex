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

from behave import given

from ecs_composex.common.settings import ComposeXSettings


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
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.input_file_arg: cases_path,
        }
    )


@given("I want to create a VPC")
def step_impl(context):
    context.settings.create_vpc = True


@given("I want to create a Cluster")
def step_impl(context):
    context.settings.create_cluster = True
