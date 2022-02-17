#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to link DocDB cluster to ECS Services.
"""

from ecs_composex.common import LOG
from ecs_composex.rds.rds_ecs import import_dbs
from ecs_composex.rds_resources_settings import handle_new_tcp_resource


def docdb_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map new and lookup resources to ECS Services

    :param dict resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for resource_name, resource in resources.items():
        LOG.info(f"{resource.module_name}.{resource_name} - Linking to services")
        if not resource.mappings and resource.cfn_resource:
            handle_new_tcp_resource(
                resource,
                res_root_stack,
                port_parameter=resource.db_port_parameter,
                sg_parameter=resource.db_sg_parameter,
                secret_parameter=resource.db_secret_arn_parameter,
            )
        elif resource.mappings and not resource.cfn_resource:
            import_dbs(resource, settings, mapping_name=resource.mapping_key)
