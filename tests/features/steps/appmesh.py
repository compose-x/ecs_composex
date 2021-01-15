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

from behave import then
from pytest import raises
from troposphere import Template
from troposphere.appmesh import Mesh

from ecs_composex.appmesh.appmesh_mesh import Mesh as AppMesh
from ecs_composex.common import LOG
from ecs_composex.common.stacks import ComposeXStack
from tests.features.steps.common import *


@then("I should have a mesh created")
def step_impl(context):
    """
    Function to verify a mesh was created

    :param context:
    """
    full_stack = generate_full_template(context.settings)
    assert isinstance(full_stack.stack_template, Template)
    mesh = full_stack.stack_template.resources[AppMesh.mesh_title]
    LOG.info(type(mesh))
    assert isinstance(mesh, Mesh)


@then("I should not have a mesh created")
def step_impl(context):
    """
    Function to verify a mesh was created

    :param context:
    """
    full_template = context.root_stack.stack_template
    assert isinstance(full_template, Template)
    services_stack = full_template.resources["services"]
    assert issubclass(type(services_stack), ComposeXStack)
    services_resources = services_stack.stack_template.resources
    with raises(KeyError):
        mesh = services_resources[AppMesh.mesh_title]


@then("I should not have a mesh")
def step_impl(context):
    """
    Asserts that no mesh got created.

    :param context:
    """
    full_template = generate_full_template(context.settings).stack_template
    assert isinstance(full_template, Template)
    services_stack = full_template.resources["services"]
    assert issubclass(type(services_stack), ComposeXStack)
    services_resources = services_stack.stack_template.resources
    print(services_resources.keys())
    assert AppMesh.mesh_title not in services_resources.keys()


@then("I should get error raised")
def step_impl(context):
    """
    Function to ensure we raise errors on mistakes
    """
    with raises((ValueError, KeyError)):
        full_template = generate_full_template(context.settings)
