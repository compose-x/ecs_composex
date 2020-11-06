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
from ecs_composex.rds.rds_aws import validate_rds_lookup, lookup_rds_resource
from ecs_composex.rds.rds_perms import (
    add_secret_to_container,
    define_db_secret_import,
    add_rds_policy,
    add_security_group_ingress,
)


def handle_new_dbs_to_services(db, secret_import, target):
    valid_ones = [
        service for service in target[2] if service not in target[0].ignored_services
    ]
    for service in valid_ones:
        add_secret_to_container(db, secret_import, service.container_definition)
    add_rds_policy(target[0].template, secret_import, db.logical_name)
    add_security_group_ingress(target[0].stack, db.logical_name)


def handle_import_dbs_to_services(
    db,
    rds_mapping,
    target,
):
    if keyisset(db.logical_name, rds_mapping) and keyisset(
        "SecretArn", rds_mapping[db.logical_name]
    ):
        valid_ones = [
            service
            for service in target[2]
            if service not in target[0].ignored_services
        ]
        for service in valid_ones:
            add_secret_to_container(
                db,
                FindInMap("Rds", db.logical_name, "SecretArn"),
                service.container_definition,
            )
        add_rds_policy(
            target[0].template,
            FindInMap("Rds", db.logical_name, "SecretArn"),
            db.logical_name,
        )
    else:
        LOG.warn(
            f"Don't forget, we did not assigned access to a secret from SecretsManager for {db.logical_name}"
        )
    add_security_group_ingress(
        target[0].stack,
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


def add_new_dbs(db, rds_root_stack):
    """

    :param rds_root_stack:
    :param ecs_composex.rds.rds_stack.Rds db:
    :return:
    """
    if db.logical_name not in rds_root_stack.stack_template.resources:
        raise KeyError(f"DB {db.logical_name} not defined in RDS Root template")
    secret_import = define_db_secret_import(db.name)
    for target in db.families_targets:
        handle_new_dbs_to_services(
            db,
            secret_import,
            target,
        )


def import_dbs(db, db_mappings):
    """
    Function to go over each service defined in the DB and assign found DB settings to service

    :param ecs_composex.rds.rds_stack.Rds db:
    :param dict db_mappings:
    :return:
    """
    for target in db.families_targets:
        target[0].template.add_mapping("Rds", db_mappings)
        handle_import_dbs_to_services(
            db,
            db_mappings,
            target,
        )


def create_lookup_mappings(mappings, lookup_dbs, settings):
    """
    Function to create the RDS mappings to add to services templates

    :param dict mappings:
    :param list lookup_dbs:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for ComposeX Execution
    """
    for db in lookup_dbs:
        validate_rds_lookup(db.name, db.lookup)
        db_config = lookup_rds_resource(db.lookup, settings.session)
        if not db_config:
            LOG.warn(
                f"No RDS DB Configuration could be defined from provided lookup. Skipping {db.name}"
            )
            return
        config = create_rds_db_config_mapping(db, db_config)
        mappings.update(config)


def rds_to_ecs(rds_dbs, services_stack, res_root_stack, settings):
    """
    Function to apply onto existing ECS Templates the various settings

    :param res_root_stack:
    :param rds_dbs:
    :param services_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for ComposeX Execution
    :return:
    """
    db_mappings = {}
    new_resources = [
        rds_dbs[db_name]
        for db_name in rds_dbs
        if not rds_dbs[db_name].lookup and rds_dbs[db_name].services
    ]
    lookup_resources = [
        rds_dbs[db_name]
        for db_name in rds_dbs
        if rds_dbs[db_name].lookup and rds_dbs[db_name].services
    ]
    if new_resources and res_root_stack.title not in services_stack.DependsOn:
        services_stack.DependsOn.append(res_root_stack.title)
        LOG.info(f"Added dependency between services and {res_root_stack.title}")
    for new_res in new_resources:
        add_new_dbs(new_res, res_root_stack)
    create_lookup_mappings(db_mappings, lookup_resources, settings)
    for lookup_res in lookup_resources:
        if keyisset(lookup_res.logical_name, db_mappings):
            import_dbs(lookup_res, db_mappings)
