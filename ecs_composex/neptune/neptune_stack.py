#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
AWS DocumentDB entrypoint for ECS ComposeX
"""

from compose_x_common.aws.neptune import NEPTUNE_DB_CLUSTER_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, GetAtt, Ref, Sub
from troposphere.neptune import DBCluster as CfnDBCluster

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import (
    DatabaseXResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.iam.import_sam_policies import get_access_types
from ecs_composex.neptune.neptune_params import (
    DB_CLUSTER_NAME,
    DB_CLUSTER_RESOURCES_ARN,
    DB_ENDPOINT,
    DB_PORT,
    DB_READ_ENDPOINT,
    DB_RESOURCE_ID,
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
)
from ecs_composex.rds.rds_params import DB_CLUSTER_ARN, DB_SG
from ecs_composex.rds_resources_settings import (
    handle_new_tcp_resource,
    import_dbs,
    lookup_rds_resource,
)
from ecs_composex.resource_settings import (
    assign_new_resource_to_service,
    handle_lookup_resource,
)
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID

from .neptune_template import create_neptune_template

LOG = setup_logging()


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
        db.db_port_parameter: "Port",
        db.db_sg_parameter: "VpcSecurityGroups::0::VpcSecurityGroupId",
        db.db_cluster_arn_parameter: DB_CLUSTER_ARN.title,
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
    policies_scaffolds = get_access_types(MOD_KEY)

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        """
        Init method

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.db_sg = None
        self.db_subnets_group = None
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        self.set_override_subnets()
        self.db_sg_parameter = DB_SG
        self.db_cluster_arn_parameter = DB_CLUSTER_ARN
        self.db_port_parameter = DB_PORT

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
            self.db_port_parameter: (
                f"{self.logical_name}{DB_PORT.return_value}",
                self.cfn_resource,
                GetAtt,
                self.db_port_parameter.return_value,
            ),
            self.db_sg_parameter: (
                f"{self.logical_name}{DB_SG.return_value}",
                self.db_sg,
                GetAtt,
                self.db_sg_parameter.return_value,
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

    def to_ecs(self, settings, root_stack=None) -> None:
        LOG.info(f"{self.module_name}.{self.name} - Linking to services")
        if not self.mappings and self.cfn_resource:
            handle_new_tcp_resource(
                self,
                port_parameter=DB_PORT,
                sg_parameter=DB_SG,
            )
            assign_new_resource_to_service(
                self,
                arn_parameter=DB_CLUSTER_RESOURCES_ARN,
                access_subkeys=["NeptuneDB"],
            )
            assign_new_resource_to_service(
                self,
                arn_parameter=self.db_cluster_arn_parameter,
                access_subkeys=["DBCluster"],
            )
        elif not self.cfn_resource and self.mappings:
            import_dbs(self, settings)
            handle_lookup_resource(
                settings,
                self,
                arn_parameter=self.db_cluster_arn_parameter,
                access_subkeys=["DBCluster"],
            )
            handle_lookup_resource(
                settings,
                self,
                arn_parameter=DB_CLUSTER_RESOURCES_ARN,
                access_subkeys=["NeptuneDB"],
            )


class XStack(ComposeXStack):
    """
    Class for the Stack of x-neptune
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(
            settings, NeptuneDBCluster, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY
        )
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = build_template(
                "Root template for Neptune by ComposeX", [VPC_ID, STORAGE_SUBNETS]
            )
            super().__init__(title, stack_template, **kwargs)
            create_neptune_template(stack_template, new_resources, settings, self)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(MAPPINGS_KEY, settings.mappings):
                settings.mappings[MAPPINGS_KEY] = {}
            for resource in lookup_resources:
                resource.lookup_resource(
                    NEPTUNE_DB_CLUSTER_ARN_RE,
                    get_db_cluster_config,
                    CfnDBCluster.resource_type,
                    "rds:cluster",
                )
                resource.generate_cfn_mappings_from_lookup_properties()
                resource.generate_outputs()
                settings.mappings[MAPPINGS_KEY].update(
                    {resource.logical_name: resource.mappings}
                )
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
