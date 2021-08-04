#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Main module template to generate the RDS Root template and all stacks according to x-rds settings
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Join, Output, Ref

from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.rds.rds_db_template import generate_database_template
from ecs_composex.rds.rds_params import (
    DB_ENGINE_NAME_T,
    DB_ENGINE_VERSION_T,
    DB_NAME_T,
    DB_SNAPSHOT_ID,
)
from ecs_composex.vpc.vpc_params import (
    STORAGE_SUBNETS,
    STORAGE_SUBNETS_T,
    VPC_ID,
    VPC_ID_T,
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

    :param troposphere.Template root_template: root template to add the nested stack to
    :param ecs_composex.rds.rds_stack.Rds db: the database definition from the compose file
    :param ecs_composex.common.settings.ComposeXSettings settings:
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


def generate_rds_templates(root_tpl, new_dbs, settings):
    """
    Function to generate the RDS root template for all the DBs defined in the x-rds section of the compose file

    :param troposphere.Template root_tpl:
    :param list new_dbs:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.rds.rds_stack.XStack self_stack:
    """
    for db in new_dbs:
        add_db_stack(root_tpl, db, settings)
    return root_tpl
