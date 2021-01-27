# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from troposphere import Output
from troposphere import Ref, Join, GetAtt

from ecs_composex.common import build_template, keyisset
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.rds.rds_db_template import (
    generate_database_template,
)
from ecs_composex.rds.rds_params import (
    DB_NAME_T,
    DB_ENGINE_VERSION_T,
    DB_ENGINE_NAME_T,
    DB_SNAPSHOT_ID,
)
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    VPC_ID_T,
    STORAGE_SUBNETS,
    STORAGE_SUBNETS_T,
)


class RdsDbStack(ComposeXStack):
    """
    Class to represent a RDS Stack
    """

    def __init__(self, name, stack_template, db, **kwargs):
        self.db = db
        self.parent_template = None
        super().__init__(name, stack_template, **kwargs)


def add_db_stack(root_template, db, settings):
    """
    Function to add the DB stack to the root stack

    :param root_template: root template to add the nested stack to
    :type root_template: troposphere.Template
    :param db: the database definition from the compose file
    :type db: ecs_composex.common.compose_resources.Rds
    """
    if db.properties:
        if not all(
            x in db.properties.keys() for x in [DB_ENGINE_NAME_T, DB_ENGINE_VERSION_T]
        ):
            raise RuntimeError(
                "When using Properties you must define at least",
                [DB_ENGINE_NAME_T, DB_ENGINE_VERSION_T],
                "Got",
                db.properties.keys(),
                f"For {db.name}",
            )
        non_stack_params = {
            DB_ENGINE_NAME_T: db.properties[DB_ENGINE_NAME_T],
            DB_ENGINE_VERSION_T: db.properties[DB_ENGINE_VERSION_T],
        }
    elif db.parameters:
        if not all(x in db.parameters for x in [DB_ENGINE_NAME_T, DB_ENGINE_VERSION_T]):
            raise RuntimeError(
                "When using MacroParameters you define at least",
                [DB_ENGINE_VERSION_T, DB_ENGINE_NAME_T],
            )
        non_stack_params = {
            DB_ENGINE_NAME_T: db.parameters[DB_ENGINE_NAME_T],
            DB_ENGINE_VERSION_T: db.parameters[DB_ENGINE_VERSION_T],
        }
    else:
        raise RuntimeError(
            "You require either Properties or MacroParameters and at least"
            f"{DB_ENGINE_NAME_T} and {DB_ENGINE_VERSION_T}."
        )
    parameters = {
        VPC_ID_T: Ref(VPC_ID),
        DB_NAME_T: db.logical_name,
        ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
    }
    if db.subnets_override:
        parameters.update({STORAGE_SUBNETS_T: Join(",", Ref(db.subnets_override))})
    else:
        parameters.update({STORAGE_SUBNETS_T: Join(",", Ref(STORAGE_SUBNETS))})
    if keyisset("SnapshotIdentifier", db.properties):
        parameters.update({DB_SNAPSHOT_ID.title: db.properties["SnapshotIdentifier"]})
    elif keyisset("DBSnapshotIdentifier", db.properties):
        parameters.update({DB_SNAPSHOT_ID.title: db.properties["DBSnapshotIdentifier"]})
    parameters.update(non_stack_params)
    db_template = generate_database_template(db, settings)
    db_stack = RdsDbStack(
        db.logical_name, db=db, stack_template=db_template, stack_parameters=parameters
    )
    root_template.add_resource(db_stack)
    new_outputs = []
    for output_name in db_stack.stack_template.outputs:
        new_outputs.append(
            Output(output_name, Value=GetAtt(db.logical_name, f"Outputs.{output_name}"))
        )
    root_template.add_output(new_outputs)


def generate_rds_templates(new_dbs, settings):
    """
    Function to generate the RDS root template for all the DBs defined in the x-rds section of the compose file

    :param list new_dbs:
    :return: rds_root_template, the RDS Root template with nested stacks
    :rtype: troposphere.Template
    """
    root_tpl = build_template("RDS Root Template", [VPC_ID, STORAGE_SUBNETS])
    for db in new_dbs:
        add_db_stack(root_tpl, db, settings)
    return root_tpl
