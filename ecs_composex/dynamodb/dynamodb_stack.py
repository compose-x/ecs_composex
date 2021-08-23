#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to create the root stack for DynamoDB tables
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref

from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dynamodb.dynamodb_ecs import create_dyndb_mappings
from ecs_composex.dynamodb.dynamodb_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    TABLE_ARN,
    TABLE_NAME,
)
from ecs_composex.dynamodb.dynamodb_perms import get_access_types
from ecs_composex.dynamodb.dynamodb_template import create_dynamodb_template


class Table(XResource):
    """
    Class to represent a DynamoDB Table
    """

    policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            TABLE_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            TABLE_ARN: (
                f"{self.logical_name}{TABLE_ARN.title}",
                self.cfn_resource,
                GetAtt,
                TABLE_ARN.return_value,
            ),
        }


class XStack(ComposeXStack):
    """
    Class for Dynamodb
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Table, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = build_template("Root template for DynamoDB tables")
            super().__init__(title, stack_template, **kwargs)
            create_dynamodb_template(new_resources, stack_template, self)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            create_dyndb_mappings(
                settings.mappings[RES_KEY], lookup_resources, settings
            )
        for resource in x_resources:
            if resource.lookup:
                resource.stack = self
