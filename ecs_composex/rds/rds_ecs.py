#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to provide services with access to the RDS databases.
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap

from ecs_composex.common import add_update_mapping
from ecs_composex.rds.rds_params import (
    DB_ENDPOINT_PORT,
    DB_SECRET_ARN,
    DB_SECRET_T,
    DB_SG,
    RES_KEY,
)
from ecs_composex.rds_resources_settings import (
    add_secret_to_container,
    add_secrets_access_policy,
    add_security_group_ingress,
    handle_new_tcp_resource,
)


def handle_import_dbs_to_services(db, settings, target, mapping_name):
    """
    Function to map the Looked up DBs (DocDB and RDS) to the services.

    :param ecs_composex.rds.rds_stack.Rds db:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param tuple target:
    :param str mapping_name:
    """
    if db.db_secret_arn_parameter and keyisset(
        db.db_secret_arn_parameter, db.attributes_outputs
    ):
        valid_ones = [
            service
            for service in target[2]
            if service not in target[0].ignored_services
        ]
        for service in valid_ones:
            add_secret_to_container(
                db,
                db.attributes_outputs[db.db_secret_arn_parameter]["ImportValue"],
                service,
                target,
            )
        add_secrets_access_policy(
            target[0],
            db.attributes_outputs[db.db_secret_arn_parameter]["ImportValue"],
            db.logical_name,
        )
    add_security_group_ingress(
        target[0].stack,
        db.logical_name,
        sg_id=db.attributes_outputs[db.db_sg_parameter]["ImportValue"],
        port=db.attributes_outputs[db.db_port_parameter]["ImportValue"],
    )


def import_dbs(db, settings, mapping_name):
    """
    Function to go over each service defined in the DB and assign found DB settings to service

    :param ecs_composex.rds.rds_stack.Rds db:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param str mapping_name:
    :return:
    """
    for target in db.families_targets:
        add_update_mapping(
            target[0].template, db.mapping_key, settings.mappings[db.mapping_key]
        )
        handle_import_dbs_to_services(db, settings, target, mapping_name)


def rds_to_ecs(rds_dbs, services_stack, res_root_stack, settings):
    """
    Function to apply onto existing ECS Templates the various settings

    :param res_root_stack:
    :param rds_dbs:
    :param services_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for ComposeX Execution
    :return:
    """
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
    for new_res in new_resources:
        handle_new_tcp_resource(
            new_res,
            res_root_stack,
            port_parameter=DB_ENDPOINT_PORT,
            secret_parameter=DB_SECRET_ARN,
            sg_parameter=DB_SG,
        )
    for lookup_res in lookup_resources:
        import_dbs(lookup_res, settings, mapping_name=lookup_res.mapping_key)
