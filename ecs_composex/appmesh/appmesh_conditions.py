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

"""
AppMesh related conditions
"""

from troposphere import (
    Ref,
    Equals,
    If,
    AWS_ACCOUNT_ID,
    GetAtt,
    AWS_STACK_NAME,
)
from troposphere.appmesh import Mesh

from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID

USER_IS_SELF_CON_T = "AppMeshOwnerIsSelf"
USER_IS_SELF_CON = Equals(Ref(MESH_OWNER_ID), Ref(AWS_ACCOUNT_ID))

USE_DEFAULT_MESH_NAME_CON_T = "UseDefaultMeshNameCondition"
USE_DEFAULT_MESH_NAME_CON = Equals(Ref(MESH_NAME), MESH_NAME.Default)


def set_mesh_owner_id():
    """
    Returns the IF condition for MeshOwner

    :return: CFN Condition
    :rtype: If
    """
    return If(USER_IS_SELF_CON_T, Ref(AWS_ACCOUNT_ID), Ref(MESH_OWNER_ID))


def set_mesh_name():
    """
    Function to set the mesh name if default is passed, otherwise generate it.
    :return: If
    """
    return If(USE_DEFAULT_MESH_NAME_CON_T, Ref(AWS_STACK_NAME), Ref(MESH_NAME))


def get_mesh_name(mesh_obj):
    """
    Function to return the mesh reference based on the type of parameter mesh_obj

    :return:
    """
    if isinstance(mesh_obj, Mesh):
        return GetAtt(mesh_obj, "MeshName")
    elif isinstance(mesh_obj, Ref):
        return Ref(MESH_NAME)


def get_mesh_owner(mesh_obj):
    """
    Function to return the mesh reference based on the type of parameter mesh_obj

    :return:
    """
    if isinstance(mesh_obj, Mesh):
        return GetAtt(mesh_obj, "MeshOwner")
    return Ref(MESH_OWNER_ID)


def add_appmesh_conditions(template):
    """
    Function to add AppMesh default conditions to template

    :param troposphere.Template template: The template to add the conditions to
    """
    template.add_condition(USE_DEFAULT_MESH_NAME_CON_T, USE_DEFAULT_MESH_NAME_CON)
    template.add_condition(USER_IS_SELF_CON_T, USER_IS_SELF_CON)
