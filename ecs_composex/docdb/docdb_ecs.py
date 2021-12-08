#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to link DocDB cluster to ECS Services.
"""

from compose_x_common.compose_x_common import keyisset

from ecs_composex.docdb.docdb_params import (
    DOCDB_PORT,
    DOCDB_SECRET,
    DOCDB_SG,
    MAPPINGS_KEY,
    RES_KEY,
)
from ecs_composex.rds.rds_ecs import import_dbs
from ecs_composex.rds_resources_settings import handle_new_tcp_resource


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
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].lookup
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(
            new_res,
            res_root_stack,
            port_parameter=DOCDB_PORT,
            sg_parameter=DOCDB_SG,
            secret_parameter=DOCDB_SECRET,
        )
    for lookup_res in lookup_resources:
        if keyisset(lookup_res.logical_name, settings.mappings[RES_KEY]):
            import_dbs(
                lookup_res, settings.mappings[RES_KEY], mapping_name=MAPPINGS_KEY
            )
