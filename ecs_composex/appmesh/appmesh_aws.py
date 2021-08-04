#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to interact with AWS AppMesh API
"""

from compose_x_common.compose_x_common import keyisset

from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.common import LOG


def find_mesh_in_list(mesh_name, client, next_token=None):
    """
    Function to recursively go through meshes in case the mesh exists but we don't know the account Id

    :param mesh_name: Name of the mesh
    :param next_token: token for next api call
    :return:
    """
    if next_token is not None:
        mesh_r = client.list_meshes(nexToken=next_token)
    else:
        mesh_r = client.list_meshes()
    if not keyisset("meshes", mesh_r):
        return {}
    for mesh in mesh_r["meshes"]:
        if mesh["meshName"] == mesh_name:
            mesh_info = {
                MESH_NAME.title: mesh["meshName"],
                MESH_OWNER_ID.title: mesh["meshOwner"],
            }
            LOG.info(
                f"Found shared mesh {mesh_name} owned by {mesh_info[MESH_OWNER_ID.title]}"
            )
            return mesh_info
    if keyisset("nextToken", mesh_r):
        return find_mesh_in_list(mesh_name, client, mesh_r["nextToken"])


def lookup_mesh_by_name(session, mesh_name, mesh_owner=None):
    """
    Function to figure out whether the mesh exists or not.

    :param str mesh_name:
    :param boto3.session.Session session:
    :param str mesh_owner:
    :return:
    """
    r_params = {
        "meshName": mesh_name,
    }
    if mesh_owner is not None:
        r_params["meshOwner"] = mesh_owner
    client = session.client("appmesh")
    try:
        mesh_r = client.describe_mesh(**r_params)["mesh"]
        mesh_info = {
            MESH_NAME.title: mesh_r["meshName"],
            MESH_OWNER_ID.title: mesh_r["metadata"]["meshOwner"],
        }
        LOG.info(f"Found mesh {mesh_name} owned by {mesh_info[MESH_OWNER_ID.title]}")
        return mesh_info
    except client.exceptions.NotFoundException:
        LOG.info(
            f"No mesh {mesh_name} found owned with current details. Looking for shared meshes."
        )
        mesh_info = find_mesh_in_list(mesh_name, client)
        return mesh_info
