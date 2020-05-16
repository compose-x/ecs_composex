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
Main module template to generate the RDS Root template and all stacks according to x-rds settings
"""

from troposphere import Ref, Join

from ecs_composex.common import build_template, validate_kwargs
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.tagging import add_all_tags, generate_tags_parameters
from ecs_composex.rds.rds_db_template import (
    generate_database_template,
    create_db_subnet_group,
)
from ecs_composex.rds.rds_params import (
    RES_KEY,
    DBS_SUBNET_GROUP_T,
    DB_NAME_T,
    DB_ENGINE_VERSION_T,
    DB_ENGINE_NAME_T,
)
from ecs_composex.vpc.vpc_conditions import (
    USE_VPC_MAP_ID_CON_T,
    USE_VPC_MAP_ID_CON,
    NOT_USE_VPC_MAP_ID_CON_T,
    NOT_USE_VPC_MAP_ID_CON,
)
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    VPC_ID_T,
    VPC_MAP_ID,
    STORAGE_SUBNETS,
    STORAGE_SUBNETS_T,
)


def add_db_stack(root_template, dbs_subnet_group, db_name, db, **kwargs):
    """
    Function to add the DB stack to the root stack

    :param dbs_subnet_group: Subnet group for DBs
    :type dbs_subnet_group: troposphere.rds.DBSubnetGroup
    :param root_template: root template to add the nested stack to
    :type root_template: troposphere.Template
    :param db_name: name of the DB as defined in the x-rds section
    :type db_name: str
    :param db: the database definition from the compose file
    :type db: dict
    :param kwargs: extra arguments
    """
    props = db["Properties"]
    required_props = [DB_ENGINE_NAME_T, DB_ENGINE_VERSION_T]
    validate_kwargs(required_props, props)
    non_stack_params = {
        DB_ENGINE_NAME_T: props[DB_ENGINE_NAME_T],
        DB_ENGINE_VERSION_T: props[DB_ENGINE_VERSION_T],
    }
    parameters = {
        VPC_ID_T: Ref(VPC_ID),
        DBS_SUBNET_GROUP_T: Ref(dbs_subnet_group),
        DB_NAME_T: db_name,
        STORAGE_SUBNETS_T: Join(",", Ref(STORAGE_SUBNETS)),
        ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
    }
    parameters.update(non_stack_params)
    db_template = generate_database_template(db_name, db, **kwargs)
    if db_template is None:
        return
    root_template.add_resource(
        ComposeXStack(
            db_name, stack_template=db_template, Parameters=parameters, **kwargs
        )
    )


def init_rds_root_template():
    """
    Function to generate the root template for RDS

    :return: template
    :rtype: troposphere.Template
    """
    template = build_template(
        "RDS Root Template", [VPC_MAP_ID, VPC_ID, STORAGE_SUBNETS]
    )
    template.add_condition(USE_VPC_MAP_ID_CON_T, USE_VPC_MAP_ID_CON)
    template.add_condition(NOT_USE_VPC_MAP_ID_CON_T, NOT_USE_VPC_MAP_ID_CON)
    return template


def generate_rds_templates(compose_content, tags=None, **kwargs):
    """
    Function to generate the RDS root template for all the DBs defined in the x-rds section of the compose file

    :param compose_content: the docker compose file content
    :type compose_content: dict
    :param kwargs: extra parameters
    :param tags: tags and parameters to add to the resources
    :type tags: tuple

    :return: rds_root_template, the RDS Root template with nested stacks
    :rtype: troposphere.Template
    """
    root_tpl = init_rds_root_template()
    dbs_subnet_group = create_db_subnet_group(root_tpl)
    if tags is None:
        tags = generate_tags_parameters(compose_content)
    section = compose_content[RES_KEY]
    for db_name in section:
        add_db_stack(
            root_tpl, dbs_subnet_group, db_name, section[db_name], **kwargs,
        )
    add_all_tags(root_tpl, tags)
    return root_tpl
