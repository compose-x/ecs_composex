# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to create the root stack for DynamoDB tables
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from botocore.exceptions import ClientError
from compose_x_common.aws.dynamodb import TABLE_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.dynamodb import Table as CfnTable

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.dynamodb.dynamodb_params import TABLE_ARN, TABLE_NAME
from ecs_composex.dynamodb.dynamodb_template import create_dynamodb_template

LOG = setup_logging()


def get_dynamodb_table_config(table, account_id, resource_id):
    """

    :param Table table:
    :param str account_id:
    :param str resource_id:
    :return:
    """

    table_attributes_mapping = {
        TABLE_NAME: "TableName",
        TABLE_ARN: "TableArn",
    }
    client = table.lookup_session.client("dynamodb")
    try:
        table_r = client.describe_table(TableName=resource_id)["Table"]
        table_config = attributes_to_mapping(table_r, table_attributes_mapping)
        return table_config
    # except client.exceptions.ResourceNotFoundException:
    #     raise
    except ClientError as error:
        LOG.error(error)
        raise


class Table(ApiXResource):
    """
    Class to represent a DynamoDB Table
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.arn_parameter = TABLE_ARN
        self.ref_parameter = TABLE_NAME
        self.default_cloudmap_settings = {
            "ReturnValues": {
                TABLE_NAME.title: TABLE_NAME.title,
                TABLE_ARN.title: TABLE_ARN.title,
            }
        }

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


def resolve_lookup(
    lookup_resources: list[Table], settings: ComposeXSettings, module: XResourceModule
) -> None:
    """
    Lookup AWS Resource

    :param list[Table] lookup_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param XResourceModule module:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            TABLE_ARN_RE,
            get_dynamodb_table_config,
            CfnTable.resource_type,
            "dynamodb:table",
        )
        LOG.info(f"{module.res_key}.{resource.name} - Matched to {resource.arn}")
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


class XStack(ComposeXStack):
    """
    Class for Dynamodb
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        set_resources(settings, Table, module)
        x_resources = settings.compose_content[module.res_key].values()
        lookup_resources = set_lookup_resources(x_resources)
        if lookup_resources:
            resolve_lookup(lookup_resources, settings, module)
        new_resources = set_new_resources(x_resources, False)
        if new_resources:
            stack_template = build_template("Root template for DynamoDB tables")
            super().__init__(title, stack_template, **kwargs)
            create_dynamodb_template(new_resources, stack_template, self)
        else:
            self.is_void = True
        for resource in x_resources:
            if resource.lookup:
                resource.stack = self
