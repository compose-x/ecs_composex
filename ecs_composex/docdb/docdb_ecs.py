#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from ecs_composex.common import keyisset
from ecs_composex.common import LOG
from ecs_composex.docdb.docdb_params import DOCDB_PORT
from ecs_composex.tcp_resources_settings import handle_new_tcp_resource
from ecs_composex.rds.rds_ecs import (
    import_dbs,
    lookup_rds_resource,
    validate_rds_lookup,
    DB_SECRET_T,
)


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
    db_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].lookup
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(new_res, res_root_stack, DOCDB_PORT)
    create_lookup_mappings(db_mappings, lookup_resources, settings)
    for lookup_res in lookup_resources:
        if keyisset(lookup_res.logical_name, db_mappings):
            import_dbs(lookup_res, db_mappings, mapping_name="DocDb")
