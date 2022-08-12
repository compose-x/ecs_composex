# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
AWS DocumentDB entrypoint for ECS ComposeX
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule, ModManager

from compose_x_common.aws.neptune import NEPTUNE_DB_CLUSTER_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, GetAtt, Ref, Sub
from troposphere.neptune import DBCluster as CfnDBCluster

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.network_x_resources import DatabaseXResource
from ecs_composex.neptune.neptune_params import (
    DB_CLUSTER_RESOURCES_ARN,
    DB_ENDPOINT,
    DB_PORT,
    DB_READ_ENDPOINT,
    DB_RESOURCE_ID,
)
from ecs_composex.neptune.neptune_template import create_neptune_template
from ecs_composex.rds.rds_params import DB_CLUSTER_ARN, DB_CLUSTER_NAME, DB_SG
from ecs_composex.rds_resources_settings import (
    handle_new_tcp_resource,
    import_dbs,
    lookup_rds_resource,
)
from ecs_composex.resource_settings import link_resource_to_services
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID

from .neptune_template import create_neptune_template


def get_db_cluster_config(db, account_id, resource_id):
    client = db.lookup_session.client("neptune")
    try:
        db_config_r = client.describe_db_clusters(
            DBClusterIdentifier=db.arn,
            Filters=[
                {
                    "Name": "engine",
                    "Values": [
                        "neptune",
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
        db.db_cluster_arn_parameter: DB_CLUSTER_ARN.title,
        db.db_cluster_ro_endpoint_param: DB_READ_ENDPOINT.return_value,
        db.db_cluster_endpoint_param: db.db_cluster_endpoint_param.return_value,
        db.ref_parameter: "DBClusterIdentifier",
    }
    config = attributes_to_mapping(db_cluster, attributes_mappings)
    config[
        DB_CLUSTER_RESOURCES_ARN
    ] = f"{config[DB_CLUSTER_ARN].replace('rds', 'neptune-db', 1)}/*"
    return config


class NeptuneDBCluster(DatabaseXResource):
    """
    Class to manage Neptune Cluster
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
        self.db_sg = None
        self.db_subnets_group = None
        super().__init__(name, definition, module, settings)
        self.set_override_subnets()
        self.security_group_param = DB_SG
        self.db_cluster_arn_parameter = DB_CLUSTER_ARN
        self.port_param = DB_PORT
        self.db_cluster_ro_endpoint_param = DB_READ_ENDPOINT
        self.db_cluster_endpoint_param = DB_ENDPOINT
        self.ref_parameter = DB_CLUSTER_NAME

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            DB_CLUSTER_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            DB_RESOURCE_ID: (
                f"{self.logical_name}{DB_RESOURCE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                DB_RESOURCE_ID.return_value,
            ),
            self.db_cluster_arn_parameter: (
                f"{self.logical_name}{self.db_cluster_arn_parameter.title}",
                self.cfn_resource,
                Sub,
                f"arn:${{{AWS_PARTITION}}}:rds:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                f"${{{self.cfn_resource.title}}}",
            ),
            DB_CLUSTER_RESOURCES_ARN: (
                f"{self.logical_name}{DB_CLUSTER_RESOURCES_ARN.title}",
                self.cfn_resource,
                Sub,
                f"arn:${{{AWS_PARTITION}}}:neptune-db:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                f"${{{self.cfn_resource.title}.{DB_RESOURCE_ID.return_value}}}",
            ),
            DB_ENDPOINT: (
                f"{self.logical_name}{DB_ENDPOINT.return_value}",
                self.cfn_resource,
                GetAtt,
                DB_ENDPOINT.return_value,
            ),
            DB_READ_ENDPOINT: (
                f"{self.logical_name}{DB_READ_ENDPOINT.return_value}",
                self.cfn_resource,
                GetAtt,
                DB_READ_ENDPOINT.return_value,
            ),
            self.port_param: (
                f"{self.logical_name}{DB_PORT.return_value}",
                self.cfn_resource,
                GetAtt,
                self.port_param.return_value,
            ),
            self.security_group_param: (
                f"{self.logical_name}{DB_SG.return_value}",
                self.db_sg,
                GetAtt,
                self.security_group_param.return_value,
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

    def to_ecs(
        self,
        settings: ComposeXSettings,
        modules: ModManager,
        root_stack: ComposeXStack = None,
    ) -> None:
        LOG.info(f"{self.module.res_key}.{self.name} - Linking to services")
        if not self.mappings and self.cfn_resource:
            handle_new_tcp_resource(
                self, port_parameter=DB_PORT, sg_parameter=DB_SG, settings=settings
            )
            link_resource_to_services(
                settings,
                self,
                arn_parameter=DB_CLUSTER_RESOURCES_ARN,
                access_subkeys=["NeptuneDB"],
            )
            link_resource_to_services(
                settings,
                self,
                arn_parameter=self.db_cluster_arn_parameter,
                access_subkeys=["DBCluster"],
            )
        elif not self.cfn_resource and self.mappings:
            import_dbs(self, settings)
            link_resource_to_services(
                settings,
                self,
                arn_parameter=self.db_cluster_arn_parameter,
                access_subkeys=["DBCluster"],
            )
            link_resource_to_services(
                settings,
                self,
                arn_parameter=DB_CLUSTER_RESOURCES_ARN,
                access_subkeys=["NeptuneDB"],
            )


class XStack(ComposeXStack):
    """
    Class for the Stack of x-neptune
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            if not keyisset(module.mapping_key, settings.mappings):
                settings.mappings[module.mapping_key] = {}
            for resource in module.lookup_resources:
                resource.lookup_resource(
                    NEPTUNE_DB_CLUSTER_ARN_RE,
                    get_db_cluster_config,
                    CfnDBCluster.resource_type,
                    "rds:cluster",
                )
                resource.generate_cfn_mappings_from_lookup_properties()
                resource.generate_outputs()
                settings.mappings[module.mapping_key].update(
                    {resource.logical_name: resource.mappings}
                )
        if module.new_resources:
            stack_template = build_template(
                "Root template for Neptune by ComposeX", [VPC_ID, STORAGE_SUBNETS]
            )
            super().__init__(title, stack_template, **kwargs)
            create_neptune_template(
                stack_template, module.new_resources, settings, self
            )
        else:
            self.is_void = True

        for resource in module.resources_list:
            resource.stack = self
