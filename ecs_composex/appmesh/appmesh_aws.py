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
Module to interact with AWS AppMesh API
"""

from ecs_composex.appmesh.appmesh_params import MESH_NAME, MESH_OWNER_ID
from ecs_composex.common import LOG, keyisset


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
