# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
AWS DocumentDB entrypoint for ECS ComposeX
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.aws.rds import RDS_DB_CLUSTER_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, GetAtt, Ref, Sub
from troposphere.docdb import DBCluster as CfnDBCluster

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.network_x_resources import DatabaseXResource
from ecs_composex.docdb.docdb_params import (
    DOCDB_ID,
    DOCDB_NAME,
    DOCDB_PORT,
    DOCDBC_ENDPOINT,
    DOCDBC_READ_ENDPOINT,
)
from ecs_composex.docdb.docdb_template import (
    create_docdb_template,
    init_doc_db_template,
)
from ecs_composex.rds.rds_params import DB_CLUSTER_ARN, DB_SECRET_ARN, DB_SG
from ecs_composex.rds_resources_settings import lookup_rds_resource, lookup_rds_secret
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS


def get_db_cluster_config(db, account_id, resource_id):
    """

    :para DocDb db:
    :param account_id:
    :param resource_id:
    :return:
    """
    client = db.lookup_session.client("docdb")
    try:
        db_config_r = client.describe_db_clusters(
            DBClusterIdentifier=db.arn,
            Filters=[
                {
                    "Name": "engine",
                    "Values": [
                        "docdb",
                    ],
                },
            ],
        )["DBClusters"]
        db_cluster = db_config_r[0]
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
        db.port_param: "Port",
        db.security_group_param: "VpcSecurityGroups::0::VpcSecurityGroupId",
        db.db_cluster_arn_parameter: "DBClusterArn",
        db.db_cluster_endpoint_param: "Endpoint",
        db.db_cluster_ro_endpoint_param: "ReaderEndpoint",
    }
    config = attributes_to_mapping(db_cluster, attributes_mappings)
    return config


class DocDb(DatabaseXResource):
    """
    Class to manage DocDB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        """
        Init method

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.db_secret = None
        self.db_sg = None
        self.db_subnets_group = None
        super().__init__(name, definition, module, settings)
        self.support_defaults = True
        self.set_override_subnets()
        self.security_group_param = DB_SG
        self.db_secret_arn_parameter = DB_SECRET_ARN
        self.port_param = DOCDB_PORT
        self.db_cluster_arn_parameter = DB_CLUSTER_ARN
        self.ref_parameter = DOCDB_NAME
        self.arn_parameter = DB_CLUSTER_ARN
        self.db_cluster_endpoint_param = DOCDBC_ENDPOINT
        self.db_cluster_ro_endpoint_param = DOCDBC_READ_ENDPOINT

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            DOCDB_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            self.port_param: (
                f"{self.logical_name}{self.port_param.return_value}",
                self.cfn_resource,
                GetAtt,
                self.port_param.return_value,
            ),
            self.db_cluster_endpoint_param: (
                f"{self.logical_name}{self.db_cluster_endpoint_param.return_value}",
                self.cfn_resource,
                GetAtt,
                self.db_cluster_endpoint_param.return_value,
            ),
            self.db_cluster_ro_endpoint_param: (
                f"{self.logical_name}{self.db_cluster_ro_endpoint_param.return_value}",
                self.cfn_resource,
                GetAtt,
                self.db_cluster_ro_endpoint_param.return_value,
            ),
            self.db_secret_arn_parameter: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
            ),
            self.security_group_param: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                self.security_group_param.return_value,
            ),
            self.db_cluster_arn_parameter: (
                f"{self.logical_name}{self.db_cluster_arn_parameter.title}",
                self.cfn_resource,
                Sub,
                f"arn:${{{AWS_PARTITION}}}:rds:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                f"${{{self.cfn_resource.title}}}",
            ),
            DOCDB_ID: (
                f"{self.logical_name}{DOCDB_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                DOCDB_ID.return_value,
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


def resolve_lookup(
    lookup_resources: list[DocDb], settings: ComposeXSettings, module: XResourceModule
):
    """
    Lookup AWS Resources

    :param list[DocDb] lookup_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param module:
    """
    if not keyisset(module.mapping_key, settings.mappings):
        settings.mappings[module.mapping_key] = {}
    for resource in lookup_resources:
        resource.lookup_resource(
            RDS_DB_CLUSTER_ARN_RE,
            get_db_cluster_config,
            CfnDBCluster.resource_type,
            "rds:cluster",
            "cluster",
        )
        if keyisset("secret", resource.lookup):
            lookup_rds_secret(resource, resource.lookup["secret"])
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        settings.mappings[module.mapping_key].update(
            {resource.logical_name: resource.mappings}
        )


class XStack(ComposeXStack):
    """
    Class for the Stack of DocDB
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            resolve_lookup(module.lookup_resources, settings, module)

        if module.new_resources:
            stack_template = init_doc_db_template()
            super().__init__(title, stack_template, **kwargs)
            create_docdb_template(stack_template, module.new_resources, settings, self)
        else:
            self.is_void = True

        for resource in module.resources_list:
            resource.stack = self
