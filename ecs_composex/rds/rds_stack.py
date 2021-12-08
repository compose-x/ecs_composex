#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to handle AWS RDS CFN Templates creation
"""
import re

from botocore.exceptions import ClientError
from compose_x_common.aws import get_account_id
from compose_x_common.aws.rds import (
    RDS_DB_CLUSTER_ARN_RE,
    RDS_DB_ID_CLUSTER_ARN_RE,
    RDS_DB_INSTANCE_ARN_RE,
)
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.rds import DBCluster as CfnDBCluster
from troposphere.rds import DBInstance as CfnDBInstance

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.rds.rds_features import apply_extra_parameters
from ecs_composex.rds.rds_params import (
    DB_ENDPOINT_PORT,
    DB_NAME,
    DB_SECRET_ARN,
    DB_SG,
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
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
        LOG.error(f"{db.module_name}.{db.name} - Failed to retrieve configuration")
        LOG.error(error)
        raise
    attributes_mappings = {}
    if keyisset("VpcSecurityGroups", db_config_r):
        db_config_r["VpcSecurityGroups"] = [
            sg
            for sg in db_config_r["VpcSecurityGroups"]
            if keyisset("Status", sg) and sg["Status"] == "active"
        ]
    config = attributes_to_mapping(db_config_r, attributes_mappings)
    return config


def get_db_cluster_config(db, account_id, resource_id):
    client = db.lookup_session.client("rds")
    try:
        db_config_r = client.describe_db_clusters(DBClusterIdentifier=db.arn)[
            "DBClusters"
        ][0]
    except (client.exceptions.DBClusterNotFoundFault,) as error:
        LOG.error(f"{db.module_name}.{db.name} - Failed to retrieve configuration")
        LOG.error(error)
        raise
    if keyisset("VpcSecurityGroups", db_config_r):
        db_config_r["VpcSecurityGroups"] = [
            sg
            for sg in db_config_r["VpcSecurityGroups"]
            if keyisset("Status", sg) and sg["Status"] == "active"
        ]

    attributes_mappings = {
        DB_NAME.title: "DatabaseName",
        DB_ENDPOINT_PORT.return_value.replace(r".", ""): "Port",
        "VpcSecurityGroupId": "VpcSecurityGroups::0::VpcSecurityGroupId",
    }
    config = attributes_to_mapping(db_config_r, attributes_mappings)
    return config


class Rds(XResource):
    """
    Class to represent a RDS DB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        self.db_secret = None
        self.db_sg = None
        self.db_subnet_group = None
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the RDS Output attributes
        """
        self.output_properties = {
            DB_NAME: (
                self.logical_name,
                self.cfn_resource,
                Ref,
                None,
                "DbName",
            ),
            DB_ENDPOINT_PORT: (
                f"{self.logical_name}{DB_ENDPOINT_PORT}",
                self.cfn_resource,
                GetAtt,
                DB_ENDPOINT_PORT.return_value,
                DB_ENDPOINT_PORT.return_value.replace(r".", ""),
            ),
            DB_SECRET_ARN: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
                "SecretArn",
            ),
            DB_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                DB_SG.return_value,
                "VpcSecurityGroupId",
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


class XStack(ComposeXStack):
    """
    Class to handle ECS root stack specific settings
    """

    def add_xdependencies(self, root_stack, settings):
        """
        Method to handle RDS to other x- resources links.

        :param ComposeXStack root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        for name, stack in self.stack_template.resources.items():
            db = stack.db
            if db.parameters:
                apply_extra_parameters(settings, stack, db, stack.stack_template)

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Rds, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        if new_resources:
            stack_template = build_template(
                "Root stack for RDS DBs", [VPC_ID, STORAGE_SUBNETS]
            )
            super().__init__(title, stack_template, **kwargs)
            generate_rds_templates(stack_template, new_resources, settings)
            self.mark_nested_stacks()
        else:
            self.is_void = True
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
        if lookup_resources and RES_KEY not in settings.mappings:
            settings.mappings[RES_KEY] = {}
        for resource in lookup_resources:
            if keyisset("cluster", resource.lookup):
                resource.lookup_resource(
                    RDS_DB_CLUSTER_ARN_RE,
                    get_db_cluster_config,
                    CfnDBCluster.resource_type,
                    "rds:cluster",
                    "cluster",
                )
            elif keyisset("instance", resource.lookup):
                resource.lookup_resource(
                    RDS_DB_INSTANCE_ARN_RE,
                    get_db_instance_config,
                    CfnDBInstance.resource_type,
                    "rds:instance",
                    "instance",
                )
            else:
                raise KeyError(
                    f"{resource.module_name}.{resource.name} - "
                    "You must specify the cluster or instance to lookup"
                )
            if keyisset("secret", resource.lookup):
                lookup_rds_secret(resource, resource.lookup["secret"])
            settings.mappings[RES_KEY].update(
                {resource.logical_name: resource.mappings}
            )
