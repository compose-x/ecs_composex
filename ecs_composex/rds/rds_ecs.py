# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to provide services with access to the RDS databases.
"""

from troposphere import Select, FindInMap

from ecs_composex.common import LOG, keyisset
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.rds.rds_perms import (
    add_secret_to_containers,
    define_db_secret_import,
    add_rds_policy,
    add_security_group_ingress,
)
from ecs_composex.rds.rds_aws import validate_rds_lookup, lookup_rds_resource


def handle_new_dbs_to_services(
    db,
    secret_import,
    service,
    services_families,
    services_stack,
    rds_root_stack,
):
    service_family = get_service_family_name(services_families, service["name"])
    if service_family not in services_stack.stack_template.resources:
        raise AttributeError(f"No service {service_family} present in services stack")
    family_wide = True if service["name"] in services_families else False
    service_stack = services_stack.stack_template.resources[service_family]
    service_template = service_stack.stack_template
    add_secret_to_containers(
        service_template,
        db,
        secret_import,
        service["name"],
        family_wide,
    )
    add_rds_policy(service_template, secret_import, db.logical_name)
    add_security_group_ingress(service_stack, db.logical_name)
    if rds_root_stack.title not in services_stack.DependsOn:
        services_stack.add_dependencies(rds_root_stack.title)


def handle_import_dbs_to_services(
    db,
    rds_mapping,
    service,
    services_families,
    services_stack,
):
    service_family = get_service_family_name(services_families, service["name"])
    if service_family not in services_stack.stack_template.resources:
        raise AttributeError(f"No service {service_family} present in services stack")
    family_wide = True if service["name"] in services_families else False
    service_stack = services_stack.stack_template.resources[service_family]
    service_stack.stack_template.add_mapping("Rds", rds_mapping)
    service_template = service_stack.stack_template
    if keyisset(db.logical_name, rds_mapping) and keyisset(
        "SecretArn", rds_mapping[db.logical_name]
    ):
        add_secret_to_containers(
            service_template,
            db,
            FindInMap("Rds", db.logical_name, "SecretArn"),
            service["name"],
            family_wide,
        )
        add_rds_policy(
            service_template,
            FindInMap("Rds", db.logical_name, "SecretArn"),
            db.logical_name,
        )
    else:
        LOG.warn(
            f"Don't forget, we did not assigned access to a secret from SecretsManager for {db.logical_name}"
        )
    add_security_group_ingress(
        service_stack,
        db.logical_name,
        sg_id=Select(0, FindInMap("Rds", db.logical_name, "VpcSecurityGroupIds")),
        port=FindInMap("Rds", db.logical_name, "Port"),
    )


def create_rds_db_config_mapping(db, db_config):
    """

    :param db:
    :param db_config:
    :return:
    """
    mapping = {
        db.logical_name: {
            "VpcSecurityGroupIds": [
                k["VpcSecurityGroupId"]
                for k in db_config["VpcSecurityGroups"]
                if k["Status"] == "active"
            ],
            "Port": db_config["Port"],
        }
    }
    if keyisset("SecretArn", db_config):
        mapping[db.logical_name]["SecretArn"] = db_config["SecretArn"]
    return mapping


def add_new_dbs(db, rds_root_stack, db_name, services_stack, services_families):
    """

    :param rds_root_stack:
    :param ecs_composex.rds.rds_stack.Rds db:
    :param str db_name: resource  name of DB in compose file
    :param services_stack:
    :param services_families: Families definition
    :return:
    """
    if db.logical_name not in rds_root_stack.stack_template.resources:
        raise KeyError(f"DB {db.logical_name} not defined in RDS Root template")
    secret_import = define_db_secret_import(db_name)
    for service in db.services:
        handle_new_dbs_to_services(
            db,
            secret_import,
            service,
            services_families,
            services_stack,
            rds_root_stack,
        )


def import_dbs(db, db_name, db_mappings, services_families, services_stack, settings):
    """
    Function to go over each service defined in the DB and assign found DB settings to service

    :param ecs_composex.rds.rds_stack.Rds db:
    :param str db_name: Name of the DB as in compose file
    :param dict db_mappings:
    :param dict services_families:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for ComposeX Execution
    :return:
    """
    validate_rds_lookup(db.name, db.lookup)
    db_config = lookup_rds_resource(db.lookup, settings.session)
    if not db_config:
        LOG.warn(
            f"No RDS DB Configuration could be defined from provided lookup. Skipping {db_name}"
        )
        return
    db_mappings.update(create_rds_db_config_mapping(db, db_config))
    for service_def in db.services:
        handle_import_dbs_to_services(
            db,
            db_mappings,
            service_def,
            services_families,
            services_stack,
        )


def rds_to_ecs(rds_dbs, services_stack, services_families, rds_root_stack, settings):
    """
    Function to apply onto existing ECS Templates the various settings

    :param rds_root_stack:
    :param rds_dbs:
    :param services_stack:
    :param services_families: Families definition
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for ComposeX Execution
    :return:
    """
    db_mappings = {}
    for db_name in rds_dbs:
        db = rds_dbs[db_name]
        if not db.services:
            LOG.warn(f"DB {db.logical_name} has no services defined.")
            continue
        if db.properties and not db.lookup and db.services:
            add_new_dbs(db, rds_root_stack, db_name, services_stack, services_families)
        elif not db.properties and db.lookup:
            import_dbs(
                db, db_name, db_mappings, services_families, services_stack, settings
            )
