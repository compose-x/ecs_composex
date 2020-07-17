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

from troposphere import Ref, Not, Equals, Condition, If, AWS_ACCOUNT_ID, GetAtt

from ecs_composex.appmesh import appmesh_params
from ecs_composex.common.cfn_conditions import define_stack_name

USE_APP_MESH_CON_T = "UseAppMeshCondition"
USE_APP_MESH_CON = Equals(
    Ref(appmesh_params.MESH_NAME), appmesh_params.MESH_NAME.Default
)

NOT_USE_APP_MESH_CON_T = "NotUseAppMeshCondition"
NOT_USE_APP_MESH_CON = Not(Condition(USE_APP_MESH_CON_T))

USER_IS_SELF_CON_T = "AppMeshOwnerIsSelf"
USER_IS_SELF_CON = Equals(
    Ref(appmesh_params.MESH_OWNER_ID), appmesh_params.MESH_OWNER_ID.Default
)


def set_mesh_owner_id():
    """
    Returns the IF condition for MeshOwner

    :return: CFN Condition
    :rtype: If
    """
    return If(
        USER_IS_SELF_CON_T, Ref(AWS_ACCOUNT_ID), Ref(appmesh_params.MESH_OWNER_ID)
    )


def set_mesh_name():
    """
    Function to set the mesh name if default is passed, otherwise generate it.
    :return: If
    """
    return If(USER_IS_SELF_CON_T, define_stack_name(), Ref(appmesh_params.MESH_NAME))


def get_mesh_name(obj):
    """
    Function to return either the Ref(mesh) or Ref(MESH_NAME).

    :parm obj: the mesh to refer to.
    :return:
    """
    return If(
        USER_IS_SELF_CON_T, GetAtt(obj, "MeshName"), Ref(appmesh_params.MESH_NAME)
    )


def get_mesh_owner(obj):
    """
    Function to return owner of the mesh.

    :parm obj: the mesh to refer to. The object must have MeshOwner in GetAtt.
    :return:
    """
    return If(
        USER_IS_SELF_CON_T, GetAtt(obj, "MeshOwner"), Ref(appmesh_params.MESH_OWNER_ID)
    )


def add_appmesh_conditions(template):
    """
    Function to add AppMesh default conditions to template

    :param troposphere.Template template: The template to add the conditions to
    """
    template.add_condition(USE_APP_MESH_CON_T, USE_APP_MESH_CON)
    template.add_condition(NOT_USE_APP_MESH_CON_T, NOT_USE_APP_MESH_CON)
    template.add_condition(USER_IS_SELF_CON_T, USER_IS_SELF_CON)
