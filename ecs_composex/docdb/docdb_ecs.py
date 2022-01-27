#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to link DocDB cluster to ECS Services.
"""

from ecs_composex.rds.rds_ecs import import_dbs
from ecs_composex.rds.rds_params import DB_ENDPOINT_PORT, DB_SECRET_ARN, DB_SG
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
            port_parameter=new_res.db_port_parameter,
            sg_parameter=new_res.db_sg_parameter,
            secret_parameter=new_res.db_secret_arn_parameter,
        )
    for lookup_res in lookup_resources:
        import_dbs(lookup_res, settings, mapping_name=lookup_res.mapping_key)
