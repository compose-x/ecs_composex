#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
DocDB
"""

from troposphere import docdb
from troposphere import Sub, Ref, GetAtt, Tags
from troposphere import AWS_NO_VALUE, AWS_STACK_NAME, AWS_REGION
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import (
    LOG,
    keyisset,
    keypresent,
    build_template,
    add_parameters,
)
from ecs_composex.vpc.vpc_params import VPC_ID, STORAGE_SUBNETS
from ecs_composex.secrets import add_db_secret, attach_to_secret_to_resource
from ecs_composex.docdb.docdb_params import DOCDB_SUBNET_GROUP_T


def init_doc_db_template():
    """
    Function to generate the base of the DocDB template.
    :return: the root template
    :rtype: troposphere.Template
    """
    template = build_template(
        "Root template for DocumentDB for ComposeX", [VPC_ID, STORAGE_SUBNETS]
    )
    subnet_group = docdb.DBSubnetGroup(
        DOCDB_SUBNET_GROUP_T,
        DBSubnetGroupDescription=Sub(f"docdb-subnets-${{{AWS_STACK_NAME}}}"),
        SubnetIds=Ref(STORAGE_SUBNETS),
        Tags=Tags(Name=Sub(f"docdb-subnets-${{{AWS_STACK_NAME}}}")),
    )
    template.add_resource(subnet_group)
    return template


def no_value_if_not_set(props, key):
    return Ref(AWS_NO_VALUE) if not keyisset(key, props) else props[key]


def set_db_cluster(db, secret, sg):
    """
    Function to parse and transform yaml definition to Troposphere

    :param ecs_composex.docdb.docdb_stack.DocDb db:
    :param troposphere.secretsmanager.Secret secret:
    :param troposphere.ec2.SecurityGroup sg:
    """

    props = {
        "AvailabilityZones": Ref(AWS_NO_VALUE),
        "DBClusterIdentifier": Ref(AWS_NO_VALUE),
        "DBSubnetGroupName": Ref(DOCDB_SUBNET_GROUP_T),
        "EngineVersion": no_value_if_not_set("EngineVersion", db.properties),
        "Port": no_value_if_not_set("Port", db.properties),
        "PreferredMaintenanceWindow": no_value_if_not_set(
            "PreferredMaintenanceWindow", db.properties
        ),
        "PreferredBackupWindow": no_value_if_not_set(
            "PreferredBackupWindow", db.properties
        ),
        "SnapshotIdentifier": no_value_if_not_set("SnapshotIdentifier", db.properties),
        "StorageEncrypted": True
        if not keypresent("StorageEncrypted", db.properties)
        else db.properties["StorageEncrypted"],
        "Tags": Tags(Name=Sub(f"docdb.{db.logical_name}")),
        "VpcSecurityGroupIds": [sg],
        "MasterUsername": f"{{{{resolve:secretsmanager:${{{secret.title}}}:SecretString:username}}}}",
        "MasterUserPassword": f"{{{{resolve:secretsmanager:${{{secret.title}}}:SecretString:password}}}}",
    }
    db.cfn_resource = docdb.DBCluster(db.logical_name, **props)


def create_docdb_template(new_resources, settings):
    """
    Function to create the root template for DocDB and associate the new resources to it.

    :param list new_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return: docdb root template
    :rtype: troposphere.Template
    """
    root_template = init_doc_db_template()
    for resource in new_resources:
        security_group = SecurityGroup(
            f"{resource.logical_name}Sg",
            GroupDescription=Sub(f"SG for docdb-{resource.logical_name}"),
            GroupName=Sub(f"${{{AWS_STACK_NAME}}}.docdb.{resource.logical_name}"),
        )
        secret = add_db_secret(root_template, resource.logical_name)
        set_db_cluster(resource, secret, security_group)
        attach_to_secret_to_resource(root_template, resource.cfn_resource, secret)
        root_template.add_resource(resource.cfn_resource)
    return root_template
