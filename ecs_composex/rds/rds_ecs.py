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

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.rds.rds_perms import (
    add_secret_to_containers,
    define_db_secret_import,
    add_rds_policy,
    add_security_group_ingress,
)


def handle_db_to_service_settings(
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


def rds_to_ecs(rdsdbs, services_stack, services_families, rds_root_stack, settings):
    """
    Function to apply onto existing ECS Templates the various settings

    :param rds_root_stack:
    :param rdsdbs:
    :param services_stack:
    :param services_families: Families definition
    :return:
    """
    for db_name in rdsdbs:
        db = rdsdbs[db_name]
        if db.logical_name not in rds_root_stack.stack_template.resources:
            raise KeyError(f"DB {db.logical_name} not defined in RDS Root template")
        if not db.services:
            LOG.warn(f"DB {db.logical_name} has no services defined.")
            continue
        secret_import = define_db_secret_import(db_name)
        for service in rdsdbs[db_name].services:
            handle_db_to_service_settings(
                db,
                secret_import,
                service,
                services_families,
                services_stack,
                rds_root_stack,
            )
