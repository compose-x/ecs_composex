#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for DynamoDB to create the root template
"""

from troposphere import MAX_OUTPUTS

from ecs_composex.common import build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dynamodb.dynamodb_table import generate_table

CFN_MAX_OUTPUTS = MAX_OUTPUTS - 10


def create_dynamodb_template(new_tables, template, self_stack):
    """
    Function to create the root DynamdoDB template.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param troposphere.Template template: Root template for DynamoDB
    :return:
    """
    mono_template = False
    if len(list(new_tables)) <= CFN_MAX_OUTPUTS:
        mono_template = True
    for table in new_tables:
        table.stack = self_stack
        generate_table(table)
        if table.cfn_resource:
            table.init_outputs()
            table.generate_outputs()
            if mono_template:
                template.add_resource(table.cfn_resource)
                template.add_output(table.outputs)
            elif not mono_template:
                table_template = build_template(
                    f"Template for DynamoDB table {table.title}"
                )
                table_template.add_resource(table)
                table_template.add_output(table.outputs)
                table_stack = ComposeXStack(
                    table.logical_name, stack_template=table_template
                )
                template.add_resource(table_stack)
    return template
