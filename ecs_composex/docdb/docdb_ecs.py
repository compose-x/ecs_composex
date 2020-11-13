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
Module to link DocDB cluster to ECS Services.
"""

from ecs_composex.docdb.docdb_params import DOCDB_PORT
from ecs_composex.tcp_resources_settings import handle_new_tcp_resource


def docdb_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map new and lookup resources to ECS Services

    :param list resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(new_res, res_root_stack, DOCDB_PORT)
