#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to link DocDB cluster to ECS Services.
"""

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.docdb.docdb_params import (
    DOCDB_PORT,
    DOCDB_SECRET,
    DOCDB_SG,
    MAPPINGS_KEY,
    RES_KEY,
)
from ecs_composex.rds.rds_ecs import (
    DB_SECRET_T,
    import_dbs,
    lookup_rds_resource,
    validate_rds_lookup,
)
from ecs_composex.tcp_resources_settings import handle_new_tcp_resource


def create_docdb_cluster_config_mapping(resource, db_config):
    """

    :param resource:
    :param db_config:
    :return:
    """
    mapping = {
        resource.logical_name: {
            "VpcSecurityGroupIds": [
                k["VpcSecurityGroupId"]
                for k in db_config["VpcSecurityGroups"]
                if k["Status"] == "active"
            ],
            "Port": db_config["Port"],
            resource.logical_name: db_config["DBClusterIdentifier"],
        }
    }
    if keyisset(DB_SECRET_T, db_config):
        mapping[resource.logical_name][DB_SECRET_T] = db_config[DB_SECRET_T]
    return mapping


def create_lookup_mappings(mappings, lookup_dbs, settings):
    """
    Function to create the DocumentDB mappings to add to services templates

    :param dict mappings:
    :param list lookup_dbs:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for ComposeX Execution
    """
    for db in lookup_dbs:
        validate_rds_lookup(db.name, db.lookup)
        db_config = lookup_rds_resource(db.lookup, settings.session)
        if not db_config:
            LOG.warning(
                f"No RDS DB Configuration could be defined from provided lookup. Skipping {db.name}"
            )
            return
        config = create_docdb_cluster_config_mapping(db, db_config)
        mappings.update(config)


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
