#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to manage top level AWS CodeGuru profiles
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.aws.cognito_userpool import USER_POOL_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.cognito import UserPool as CfnUserPool

from ecs_composex.cognito_userpool.cognito_params import (
    USERPOOL_ARN,
    USERPOOL_CUSTOM_DOMAIN,
    USERPOOL_DOMAIN,
    USERPOOL_ID,
    USERPOOL_NAME,
)
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)


def get_userpool_config(userpool, account_id, resource_id):
    """
    Retrieves the UserPool properties from AWS

    :param UserPool userpool:
    :param str account_id: unused
    :param str resource_id: The Userpool ARN
    :return:
    """
    client = userpool.lookup_session.client("cognito-idp")
    userpool_attributes_mapping = {
        USERPOOL_ARN: "UserPool::Arn",
        USERPOOL_ID: "UserPool::Id",
        USERPOOL_DOMAIN: "UserPool::Domain",
        USERPOOL_CUSTOM_DOMAIN: "UserPool::CustomDomain",
        USERPOOL_NAME: "UserPool::Name",
    }
    try:
        userpool_r = client.describe_user_pool(UserPoolId=resource_id)
        attributes = attributes_to_mapping(userpool_r, userpool_attributes_mapping)
        return attributes
    except client.exceptions:
        LOG.error("Failed to retrieve the Pool Domain. Moving on.")
    return {}


class UserPool(AwsEnvironmentResource, ApiXResource):
    """
    Class to manage AWS UserPool
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.arn_parameter = USERPOOL_ARN

    def init_outputs(self):
        self.output_properties = {
            USERPOOL_ID: (self.logical_name, self.cfn_resource, Ref, None),
            USERPOOL_ARN: (
                f"{self.logical_name}{USERPOOL_ARN.title}",
                self.cfn_resource,
                GetAtt,
                USERPOOL_ARN.return_value,
            ),
        }


def resolve_lookup(
    lookup_resources: list[UserPool],
    settings: ComposeXSettings,
    module: XResourceModule,
):
    """
    Iterates over the lookup resources and performs the lookup to create the resource mapping used in the template.

    :param list[UserPool] lookup_resources: the lookup resources to process
    :param ecs_composex.common.settings.ComposeXSettings settings: the ComposeX Execution settings.
    :param module:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            USER_POOL_RE,
            get_userpool_config,
            CfnUserPool.resource_type,
            "cognito-idp",
        )
        resource.init_outputs()
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )
        LOG.info(f"{resource.module.res_key}.{resource.name} Found in AWS Account")


class XStack(ComposeXStack):
    """
    Method to manage the elastic cache resources and root stack
    """

    def __init__(
        self, title: str, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        """
        :param str title:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """

        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)

        if module.new_resources:
            LOG.error(f"{module.res_key} does not support new resources creation yet.")
            stack_template = build_template(f"Root stack to manage {module.mod_key}")
            super().__init__(title, stack_template, **kwargs)
            self.is_void = True
        else:
            self.is_void = True
        for resource in module.resources_list:
            resource.stack = self
