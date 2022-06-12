# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
AppMesh related conditions
"""

from troposphere import AWS_ACCOUNT_ID, Equals, GetAtt, If, Ref
from troposphere.appmesh import Mesh

from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.common.cfn_params import ROOT_STACK_NAME

USER_IS_SELF_CON_T = "AppMeshOwnerIsSelf"
USER_IS_SELF_CON = Equals(Ref(MESH_OWNER_ID), MESH_OWNER_ID.Default)


def set_mesh_owner_id():
    """
    Returns the IF condition for MeshOwner

    :return: CFN Condition
    :rtype: If
    """
    return If(USER_IS_SELF_CON_T, Ref(AWS_ACCOUNT_ID), Ref(MESH_OWNER_ID))


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
    return set_mesh_owner_id()


def add_appmesh_conditions(template):
    """
    Function to add AppMesh default conditions to template

    :param troposphere.Template template: The template to add the conditions to
    """
    template.add_condition(USER_IS_SELF_CON_T, USER_IS_SELF_CON)
