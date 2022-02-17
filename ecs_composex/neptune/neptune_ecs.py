#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to link DocDB cluster to ECS Services.
"""

from ecs_composex.common import LOG
from ecs_composex.neptune.neptune_params import (
    DB_CLUSTER_RESOURCES_ARN,
    DB_PORT,
    MAPPINGS_KEY,
)
from ecs_composex.rds.rds_ecs import import_dbs
from ecs_composex.rds.rds_params import DB_SG
from ecs_composex.rds_resources_settings import handle_new_tcp_resource
from ecs_composex.resource_settings import handle_lookup_resource


def neptune_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to neptune resources to ECS Services
    Neptune needs network access, but also IAM for API calls authN and authZ,
    but the ARN for the one is different from the other, so we have to do the
    IAM mapping twice

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
                port_parameter=DB_PORT,
                sg_parameter=DB_SG,
            )
        elif not resource.cfn_resource and resource.mappings:
            import_dbs(resource, settings, mapping_name=MAPPINGS_KEY)
            handle_lookup_resource(
                settings,
                resource,
                arn_parameter=resource.db_cluster_arn_parameter,
                access_subkeys=["DBCluster"],
            )
            handle_lookup_resource(
                settings,
                resource,
                arn_parameter=DB_CLUSTER_RESOURCES_ARN,
                access_subkeys=["NeptuneDB"],
            )
