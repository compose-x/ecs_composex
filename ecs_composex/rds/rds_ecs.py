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

from ecs_composex.common import LOG, KEYISSET
from ecs_composex.rds.rds_perms import (
    add_secret_to_containers,
    define_db_secret_import,
    add_rds_policy,
    add_security_group_ingress,
)


def rds_to_ecs(rdsdbs, services_stack, rds_root_stack, **kwargs):
    """
    Function to apply onto existing ECS Templates the various settings
    :param rds_root_stack:
    :param rdsdbs:
    :param services_stack:
    :param kwargs:
    :return:
    """
    for db_name in rdsdbs:
        db_def = rdsdbs[db_name]
        if db_name not in rds_root_stack.stack_template.resources:
            raise KeyError(f"DB {db_name} not defined in RDS Root template")
        if not KEYISSET("Services", db_def):
            LOG.warn(f"DB {db_name} has no services defined.")
            continue
        secret_import = define_db_secret_import(db_name)
        for service in db_def["Services"]:
            if not service["name"] in services_stack.stack_template.resources:
                raise AttributeError(
                    f"No service {service['name']} present in services stack"
                )
            service_stack = services_stack.stack_template.resources[service["name"]]
            service_template = service_stack.stack_template
            add_secret_to_containers(service_template, db_name, secret_import)
            add_rds_policy(service_template, secret_import, db_name)
            add_security_group_ingress(service_stack, db_name)
            if rds_root_stack.title not in services_stack.DependsOn:
                services_stack.DependsOn.append(rds_root_stack.title)
