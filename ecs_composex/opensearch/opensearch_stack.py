# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule, ModManager

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, GetAtt, Ref, Sub

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.network_x_resources import DatabaseXResource
from ecs_composex.opensearch.opensearch_aws import create_opensearch_mappings
from ecs_composex.opensearch.opensearch_params import (
    OS_DOMAIN_ARN,
    OS_DOMAIN_ENDPOINT,
    OS_DOMAIN_ID,
    OS_DOMAIN_PORT,
    OS_DOMAIN_SG,
)
from ecs_composex.opensearch.opensearch_template import create_new_domains
from ecs_composex.rds.rds_params import DB_SECRET_ARN
from ecs_composex.rds_resources_settings import handle_new_tcp_resource, import_dbs
from ecs_composex.resource_settings import link_resource_to_services
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID


def define_default_key_policy():
    """
    Function to return the default KMS management policy allowing root account access.
    :return: policy
    :rtype: dict
    """
    policy = {
        "Version": "2012-10-17",
        "Id": "auto-secretsmanager-1",
        "Statement": [
            {
                "Sid": "Allow direct access to key metadata to the account",
                "Effect": "Allow",
                "Principal": {
                    "AWS": Sub(
                        f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:root"
                    )
                },
                "Action": ["opensearch:*"],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {"opensearch:CallerAccount": Ref(AWS_ACCOUNT_ID)}
                },
            }
        ],
    }
    return policy


class OpenSearchDomain(DatabaseXResource):
    """
    Class to represent the OpenSearch domain
    """

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):

        super().__init__(
            name,
            definition,
            module,
            settings,
        )
        self.subnets_param = STORAGE_SUBNETS
        self.security_group_param = OS_DOMAIN_SG
        self.db_secret_arn_parameter = DB_SECRET_ARN
        self.db_cluster_endpoint_param = OS_DOMAIN_ENDPOINT
        self.db_cluster_arn_parameter = OS_DOMAIN_ARN
        self.arn_parameter = OS_DOMAIN_ARN
        self.ref_parameter = OS_DOMAIN_ID
        self.support_defaults = True

    def init_outputs(self):
        """
        Initializes the output properties
        """
        self.output_properties = {
            OS_DOMAIN_ID: (self.logical_name, self.cfn_resource, Ref, None),
            OS_DOMAIN_ARN: (
                f"{self.logical_name}{OS_DOMAIN_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                OS_DOMAIN_ARN.return_value,
            ),
            OS_DOMAIN_ENDPOINT: (
                f"{self.logical_name}{OS_DOMAIN_ENDPOINT.return_value}",
                self.cfn_resource,
                GetAtt,
                OS_DOMAIN_ENDPOINT.return_value,
            ),
        }

    def to_ecs(
        self,
        settings: ComposeXSettings,
        modules: ModManager,
        root_stack: ComposeXStack = None,
    ) -> None:
        """
        Mapping for OpenSearch domains override from default RDS DB access
        """
        if not self.stack.is_void and self.cfn_resource and not self.mappings:
            if self.security_group:
                handle_new_tcp_resource(
                    self,
                    port_parameter=OS_DOMAIN_PORT,
                    sg_parameter=OS_DOMAIN_SG,
                    settings=settings,
                )
            link_resource_to_services(
                settings,
                self,
                arn_parameter=OS_DOMAIN_ARN,
                access_subkeys=["Http", "DBCluster"],
            )
        elif self.mappings and self.lookup_properties:
            if keyisset(OS_DOMAIN_SG.return_value, self.mappings):
                self.add_new_output_attribute(
                    OS_DOMAIN_SG,
                    (
                        f"{self.logical_name}{OS_DOMAIN_SG.return_value}",
                        self.security_group,
                        GetAtt,
                        OS_DOMAIN_SG.return_value,
                    ),
                )
                self.add_new_output_attribute(
                    OS_DOMAIN_PORT,
                    (
                        f"{self.logical_name}{OS_DOMAIN_PORT.title}",
                        OS_DOMAIN_PORT.Default,
                        OS_DOMAIN_PORT.Default,
                        False,
                    ),
                )
                self.generate_outputs()
            link_resource_to_services(
                settings,
                self,
                arn_parameter=self.arn_parameter,
                access_subkeys=["Http", "DBCluster"],
            )
            import_dbs(self, settings)


class XStack(ComposeXStack):
    """
    Class for KMS Root stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            if not keyisset(module.mapping_key, settings.mappings):
                settings.mappings[module.mapping_key] = {}
            create_opensearch_mappings(module.lookup_resources, settings)
        if module.new_resources:
            stack_template = build_template(
                "Root template for OpenSearch", [VPC_ID, STORAGE_SUBNETS]
            )
            super().__init__(title, stack_template, **kwargs)
            create_new_domains(module.new_resources, self)
        else:
            self.is_void = True

        for resource in module.resources_list:
            resource.stack = self
