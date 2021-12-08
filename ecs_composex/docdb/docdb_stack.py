#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
AWS DocumentDB entrypoint for ECS ComposeX
"""

from botocore.exceptions import ClientError
from compose_x_common.aws.rds import RDS_DB_CLUSTER_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref
from troposphere.docdb import DBCluster as CfnDBCluster

from ecs_composex.common import setup_logging
from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.docdb.docdb_params import (
    DOCDB_NAME,
    DOCDB_PORT,
    DOCDB_SECRET,
    DOCDB_SG,
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
)
from ecs_composex.docdb.docdb_template import (
    create_docdb_template,
    init_doc_db_template,
)
from ecs_composex.rds_resources_settings import lookup_rds_resource, lookup_rds_secret
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS

LOG = setup_logging()


def get_db_cluster_config(db, account_id, resource_id):
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
        DOCDB_PORT.title: "Port",
        "VpcSecurityGroupId": "VpcSecurityGroups::0::VpcSecurityGroupId",
    }
    config = attributes_to_mapping(db_cluster, attributes_mappings)
    return config


class DocDb(XResource):
    """
    Class to manage DocDB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        """
        Init method

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.db_secret = None
        self.db_sg = None
        self.db_subnets_group = None
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            DOCDB_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            DOCDB_PORT: (
                f"{self.logical_name}{DOCDB_PORT.return_value}",
                self.cfn_resource,
                GetAtt,
                DOCDB_PORT.return_value,
            ),
            DOCDB_SECRET: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
            ),
            DOCDB_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                DOCDB_SG.return_value,
            ),
        }

    def lookup_secret(self, secret_lookup):

        if keyisset("Arn", secret_lookup):
            client = self.lookup_session.client("secretsmanager")
            try:
                secret_arn = client.describe_secret(SecretId=secret_lookup["Arn"])[
                    "ARN"
                ]
            except client.exceptions.ResourceNotFoundException:
                LOG.error(
                    f"{self.module_name}.{self.name} - Secret {secret_lookup['Arn']} not found"
                )
                raise
            except ClientError as error:
                LOG.error(error)
                raise
        elif keyisset("Tags", secret_lookup):
            secret_arn = find_aws_resource_arn_from_tags_api(
                self.lookup["secret"], self.lookup_session, "secretsmanager:secret"
            )
        else:
            raise LookupError(
                f"{self.module_name}.{self.name} - Failed to find the DB Secret"
            )
        if secret_arn:
            self.mappings[DOCDB_SECRET.title] = secret_arn

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
    Class for the Stack of DocDB
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, DocDb, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = init_doc_db_template()
            super().__init__(title, stack_template, **kwargs)
            create_docdb_template(stack_template, new_resources, settings, self)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
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
                settings.mappings[RES_KEY].update(
                    {resource.logical_name: resource.mappings}
                )
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
