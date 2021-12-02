#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to manage top level AWS CodeGuru profiles
"""

from compose_x_common.aws.cognito_userpool import USER_POOL_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.cognito import UserPool as CfnUserPool

from ecs_composex.cognito_userpool.cognito_params import (
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    USERPOOL_ARN,
    USERPOOL_CUSTOM_DOMAIN,
    USERPOOL_DOMAIN,
    USERPOOL_ID,
    USERPOOL_NAME,
)
from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack

LOG = setup_logging()


def get_userpool_config(userpool, account_id, resource_id):
    client = userpool.lookup_session.client("cognito-idp")
    userpool_attributes_mapping = {
        USERPOOL_ARN.return_value: "UserPool::Arn",
        USERPOOL_ID.title: "UserPool::Id",
        USERPOOL_DOMAIN.title: "UserPool::Domain",
        USERPOOL_CUSTOM_DOMAIN.title: "UserPool::CustomDomain",
        USERPOOL_NAME.title: "UserPool::Name",
    }
    try:
        userpool_r = client.describe_user_pool(UserPoolId=resource_id)
        attributes = attributes_to_mapping(userpool_r, userpool_attributes_mapping)
        return attributes
    except client.exceptions:
        LOG.error("Failed to retrieve the Pool Domain. Moving on.")
    return {}


def create_root_template(new_resources):
    """
    Function to create the root stack template for profiles
    :param new_resources:
    :return:
    """
    root_tpl = build_template(f"Root stack to manage {MOD_KEY}")
    return root_tpl


class UserPool(XResource):
    """
    Class to manage AWS Code Guru profiles
    """

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


class XStack(ComposeXStack):
    """
    Method to manage the elastic cache resources and root stack
    """

    def __init__(self, title, settings, **kwargs):
        """
        :param str title:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        set_resources(settings, UserPool, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = create_root_template(new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
        for res in lookup_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            for resource in lookup_resources:
                resource.lookup_resource(
                    USER_POOL_RE,
                    get_userpool_config,
                    CfnUserPool.resource_type,
                    "cognito-idp",
                )
                settings.mappings[RES_KEY].update({resource.logical_name: res.mappings})
