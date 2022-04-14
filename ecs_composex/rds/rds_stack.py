# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle AWS RDS CFN Templates creation
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule


from compose_x_common.aws.rds import RDS_DB_CLUSTER_ARN_RE, RDS_DB_INSTANCE_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, GetAtt, Ref, Sub
from troposphere.rds import DBCluster as CfnDBCluster
from troposphere.rds import DBInstance as CfnDBInstance

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.network_x_resources import DatabaseXResource
from ecs_composex.rds.rds_features import apply_extra_parameters
from ecs_composex.rds.rds_params import (
    DB_CLUSTER_ARN,
    DB_CLUSTER_NAME,
    DB_ENDPOINT_ADDRESS,
    DB_ENDPOINT_PORT,
    DB_NAME,
    DB_RO_ENDPOINT_ADDRESS,
    DB_SECRET_ARN,
    DB_SG,
)
from ecs_composex.rds.rds_template import generate_rds_templates
from ecs_composex.rds_resources_settings import lookup_rds_resource, lookup_rds_secret
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID

LOG = setup_logging()


def get_db_instance_config(db, account_id, resource_id):
    """

    :param Rds db:
    :param account_id:
    :param resource_id:
    :return:
    """
    client = db.lookup_session.client("rds")
    try:
        db_config_r = client.describe_db_instances(DBInstanceIdentifier=db.arn)[
            "DBInstances"
        ][0]
    except (client.exceptions.DBInstanceNotFoundFault,) as error:
        LOG.error(f"{db.module.res_key}.{db.name} - Failed to retrieve configuration")
        LOG.error(error)
        raise
    attributes_mappings = {
        DB_NAME: "DBName",
        db.port_param: "Endpoint::Port",
        db.security_group_param: "VpcSecurityGroups::0::VpcSecurityGroupId",
        db.db_cluster_arn_parameter: "DBInstanceArn",
        db.db_cluster_endpoint_param: "Endpoint::Address",
    }
    if keyisset("VpcSecurityGroups", db_config_r):
        db_config_r["VpcSecurityGroups"] = [
            sg
            for sg in db_config_r["VpcSecurityGroups"]
            if keyisset("Status", sg) and sg["Status"] == "active"
        ]
    config = attributes_to_mapping(db_config_r, attributes_mappings)
    return config


def get_db_cluster_config(db, account_id, resource_id):
    """
    Creates the DB configuration to use then in Mappings

    :param Rds db:
    :param str account_id:
    :param str resource_id:
    :return: The config
    :rtype: dict
    """
    client = db.lookup_session.client("rds")
    try:
        db_config_r = client.describe_db_clusters(DBClusterIdentifier=db.arn)[
            "DBClusters"
        ][0]
    except (client.exceptions.DBClusterNotFoundFault,) as error:
        LOG.error(f"{db.module.res_key}.{db.name} - Failed to retrieve configuration")
        LOG.error(error)
        raise
    if keyisset("VpcSecurityGroups", db_config_r):
        db_config_r["VpcSecurityGroups"] = [
            sg
            for sg in db_config_r["VpcSecurityGroups"]
            if keyisset("Status", sg) and sg["Status"] == "active"
        ]

    attributes_mappings = {
        DB_NAME: "DatabaseName",
        db.port_param: "Port",
        db.security_group_param: "VpcSecurityGroups::0::VpcSecurityGroupId",
        db.db_cluster_arn_parameter: "DBClusterArn",
        db.db_cluster_endpoint_param: "Endpoint",
        db.db_cluster_ro_endpoint_param: "ReaderEndpoint",
    }
    config = attributes_to_mapping(db_config_r, attributes_mappings)
    return config


class Rds(DatabaseXResource):
    """
    Class to represent RDS DB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        self.db_secret = None
        self.db_sg = None
        self.db_subnet_group = None
        super().__init__(name, definition, module, settings)
        self.set_override_subnets()
        self.port_param = DB_ENDPOINT_PORT
        self.db_secret_arn_parameter = DB_SECRET_ARN
        self.security_group_param = DB_SG
        self.db_cluster_arn_parameter = DB_CLUSTER_ARN
        self.ref_parameter = DB_CLUSTER_NAME
        self.db_cluster_endpoint_param = DB_ENDPOINT_ADDRESS
        self.db_cluster_ro_endpoint_param = DB_RO_ENDPOINT_ADDRESS

    def init_outputs(self):
        """
        Method to init the RDS Output attributes
        """
        self.output_properties = {
            DB_CLUSTER_NAME: (
                self.logical_name,
                self.cfn_resource,
                Ref,
                None,
                "DbName",
            ),
            self.db_cluster_arn_parameter: (
                f"{self.logical_name}{self.db_cluster_arn_parameter.title}",
                self.cfn_resource,
                Sub,
                f"arn:${{{AWS_PARTITION}}}:rds:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                f"${{{self.cfn_resource.title}}}",
            ),
            self.port_param: (
                f"{self.logical_name}{self.port_param.return_value}",
                self.cfn_resource,
                GetAtt,
                self.port_param.return_value,
                self.port_param.return_value.replace(r".", ""),
            ),
            self.db_secret_arn_parameter: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
                "SecretArn",
            ),
            self.security_group_param: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                self.security_group_param.return_value,
                "VpcSecurityGroupId",
            ),
            self.db_cluster_endpoint_param: (
                f"{self.logical_name}{self.db_cluster_endpoint_param.title}",
                self.cfn_resource,
                GetAtt,
                self.db_cluster_endpoint_param.return_value,
                self.db_cluster_endpoint_param.return_value.replace(".", ""),
            ),
            self.db_cluster_ro_endpoint_param: (
                f"{self.logical_name}{self.db_cluster_ro_endpoint_param.title}",
                self.cfn_resource,
                GetAtt,
                self.db_cluster_ro_endpoint_param.return_value,
                self.db_cluster_ro_endpoint_param.return_value.replace(".", ""),
            ),
        }

    def lookup_resource(
        self,
        arn_re,
        native_lookup_function,
        cfn_resource_type,
        tagging_api_id,
        subattribute_key=None,
    ):
        """
        Method to self-identify properties
        :return:
        """
        lookup_rds_resource(
            self,
            arn_re,
            native_lookup_function,
            cfn_resource_type,
            tagging_api_id,
            subattribute_key,
        )

    def handle_x_dependencies(self, settings, root_stack=None):
        """
        Handles x-rds to other x-resource dependencies and features
        :param settings:
        :param root_stack:
        :return:
        """
        if self.parameters:
            apply_extra_parameters(
                settings, self, self.stack.stack_template.resources[self.name]
            )


class XStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        set_resources(settings, Rds, module)
        x_resources = settings.compose_content[module.res_key].values()
        new_resources = set_new_resources(x_resources, True)
        lookup_resources = set_lookup_resources(x_resources)
        if new_resources:
            stack_template = build_template(
                "Root stack for RDS DBs", [VPC_ID, STORAGE_SUBNETS]
            )
            super().__init__(title, stack_template, **kwargs)
            generate_rds_templates(stack_template, new_resources, settings)
            self.mark_nested_stacks()
        else:
            self.is_void = True
        for resource in settings.compose_content[module.res_key].values():
            resource.stack = self
        if lookup_resources and module.mapping_key not in settings.mappings:
            settings.mappings[module.mapping_key] = {}
        for resource in lookup_resources:
            if keyisset("cluster", resource.lookup):
                resource.lookup_resource(
                    RDS_DB_CLUSTER_ARN_RE,
                    get_db_cluster_config,
                    CfnDBCluster.resource_type,
                    "rds:cluster",
                    "cluster",
                )
            elif keyisset("db", resource.lookup):
                resource.lookup_resource(
                    RDS_DB_INSTANCE_ARN_RE,
                    get_db_instance_config,
                    CfnDBInstance.resource_type,
                    "rds:db",
                    "db",
                )
            else:
                raise KeyError(
                    f"{resource.module.res_key}.{resource.name} - "
                    "You must specify the cluster or instance to lookup"
                )
            if keyisset("secret", resource.lookup):
                lookup_rds_secret(resource, resource.lookup["secret"])

            resource.generate_cfn_mappings_from_lookup_properties()
            resource.generate_outputs()
            settings.mappings[module.mapping_key].update(
                {resource.logical_name: resource.mappings}
            )
