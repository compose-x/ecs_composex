# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for DynamoDB to create the root template
"""

from troposphere import MAX_OUTPUTS, Ref, Tags, dynamodb

import ecs_composex.common.troposphere_tools
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dynamodb import metadata
from ecs_composex.resources_import import import_record_properties

from ..common.troposphere_tools import add_outputs, add_resource, build_template
from .dynamodb_autoscaling import add_autoscaling

CFN_MAX_OUTPUTS = MAX_OUTPUTS - 10


def define_table(table, template):
    """
    Function to create the DynamoDB table resource

    :param table:
    :type table: ecs_composex.common.compose_resources.Table
    """
    table_props = import_record_properties(table.properties, dynamodb.Table)
    table_props.update(
        {
            "Metadata": metadata,
            "Tags": Tags(
                Name=table.name,
                ResourceName=table.logical_name,
                CreatedByComposex=True,
                RootStackName=Ref(ROOT_STACK_NAME),
            ),
        }
    )
    cfn_table = dynamodb.Table(table.logical_name, **table_props)
    table.cfn_resource = cfn_table
    if table.scaling:
        add_autoscaling(table, template)
    table.init_outputs()
    table.generate_outputs()
    add_resource(template, table.cfn_resource)
    add_outputs(template, table.outputs)


def create_dynamodb_template(new_tables, template, self_stack):
    """
    Function to create the root DynamdoDB template.

    :param list new_tables:
    :param troposhere.Template template:
    :param ComposeXStack self_stack:
    :return:
    """
    total_outputs = sum(len(table.attributes_outputs.keys()) for table in new_tables)
    mono_template = False
    if total_outputs <= CFN_MAX_OUTPUTS:
        mono_template = True
    for table in new_tables:
        if mono_template:
            table.stack = self_stack
            define_table(table, template)
        elif not mono_template:
            table_template = build_template(
                f"Template for DynamoDB table {table.title}"
            )
            table_stack = ComposeXStack(
                table.logical_name, stack_template=table_template
            )
            table.stack = table_stack
            define_table(table, table_template)
            template.add_resource(table_stack)

    return template
