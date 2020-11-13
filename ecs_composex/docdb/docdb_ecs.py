#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from troposphere import Ref, GetAtt

from ecs_composex.common import add_parameters
from ecs_composex.rds.rds_ecs import handle_new_dbs_to_services
from ecs_composex.docdb.docdb_params import DOCDB_PORT, DOCDB_SG


def handle_new_resources(db, res_root_stack):
    """
    Function to implement the link between services and new DocDB clusters

    :param ecs_composex.docdb.docdb_stack.DocDb db:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    """
    db.set_resource_arn(res_root_stack.title)
    db.set_ref_resource_value(res_root_stack.title)
    db.set_resource_arn_parameter()
    if db.logical_name not in res_root_stack.stack_template.resources:
        raise KeyError(f"DB {db.logical_name} not defined in DocDB Root template")

    secret_import = db.get_resource_attribute_value(
        db.db_secret.title, res_root_stack.title
    )
    secret_parameter = db.get_resource_attribute_parameter(db.db_secret.title)

    sg_import = db.get_resource_attribute_value(DOCDB_PORT.title, res_root_stack.title)
    sg_param = db.get_resource_attribute_parameter(DOCDB_SG.title)

    port_import = db.get_resource_attribute_value(
        DOCDB_PORT.title, res_root_stack.title
    )
    port_param = db.get_resource_attribute_parameter(DOCDB_PORT.title)
    for target in db.families_targets:
        add_parameters(target[0].template, [secret_parameter, sg_param, port_param])
        target[0].stack.Parameters.update(
            {
                secret_parameter.title: secret_import,
                sg_param.title: sg_import,
                port_param.title: port_import,
            }
        )
        handle_new_dbs_to_services(
            db, Ref(secret_parameter), Ref(sg_param), target, port=Ref(port_param)
        )
        if res_root_stack.title not in target[0].stack.DependsOn:
            target[0].stack.DependsOn.append(res_root_stack.title)


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
    for new_res in new_resources:
        handle_new_resources(new_res, res_root_stack)
