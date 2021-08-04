#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
DocDB
"""

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import AWS_NO_VALUE, AWS_STACK_NAME, GetAtt, Ref, Sub, Tags, docdb
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import build_template
from ecs_composex.resources_import import import_record_properties
from ecs_composex.secrets import (
    add_db_dependency,
    add_db_secret,
    attach_to_secret_to_resource,
)
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID


def init_doc_db_template():
    """
    Function to generate the base of the DocDB template.
    :return: the root template
    :rtype: troposphere.Template
    """
    template = build_template(
        "Root template for DocumentDB for ComposeX", [VPC_ID, STORAGE_SUBNETS]
    )
    return template


def no_value_if_not_set(props, key, is_bool=False):
    if not is_bool:
        return Ref(AWS_NO_VALUE) if not keyisset(key, props) else props[key]
    else:
        return Ref(AWS_NO_VALUE) if not keypresent(key, props) else props[key]


def add_parameters_group(db):
    """
    Function to create the DBClusterParameterGroup to associate with the cluster

    :param ecs_composex.docdb.docdb_stack.DocDb db:
    :return: parameter group
    :rtype: docdb.DBClusterParameterGroup
    """
    props = import_record_properties(
        db.parameters["DBClusterParameterGroup"], docdb.DBClusterParameterGroup
    )
    return docdb.DBClusterParameterGroup(f"{db.logical_name}ParametersGroup", **props)


def set_db_cluster(template, db, secret, sgs):
    """
    Function to parse and transform yaml definition to Troposphere

    :param ecs_composex.docdb.docdb_stack.DocDb db:
    :param troposphere.secretsmanager.Secret secret:
    :param list<roposphere.ec2.SecurityGroup> sgs:
    """
    parameter_group = None
    props = import_record_properties(db.properties, docdb.DBCluster)
    if not keypresent("StorageEncrypted", props):
        props["StorageEncrypted"] = True
    props.update(
        {
            "VpcSecurityGroupIds": sgs,
            "MasterUsername": Sub(
                f"{{{{resolve:secretsmanager:${{{secret.title}}}:SecretString:username}}}}"
            ),
            "MasterUserPassword": Sub(
                f"{{{{resolve:secretsmanager:${{{secret.title}}}:SecretString:password}}}}"
            ),
            "DBSubnetGroupName": Ref(db.db_subnets_group),
        }
    )
    if db.parameters and keyisset("DBClusterParameterGroup", db.parameters):
        parameter_group = template.add_resource(add_parameters_group(db))
        props["DBClusterParameterGroupName"] = Ref(parameter_group)
    db.cfn_resource = docdb.DBCluster(db.logical_name, **props)
    template.add_resource(db.cfn_resource)


def add_db_instances(template, db):
    """
    Function to add DB Instances either based on properties or default.
    Default is to add one DB Instance, the smallest size there is.

    :param troposphere.Template template:
    :param ecs_composex.docdb.docdb_stack.DocDb db:
    :return:
    """
    if not db.parameters or not keyisset("Instances", db.parameters):
        template.add_resource(
            docdb.DBInstance(
                f"{db.logical_name}DefaultInstance",
                DBClusterIdentifier=Ref(db.cfn_resource),
                DBInstanceClass="db.t3.medium",
                DBInstanceIdentifier=Ref(AWS_NO_VALUE),
                Tags=Tags(DocDbCluster=Ref(db.cfn_resource)),
            )
        )
    else:
        for count, instance in enumerate(db.parameters["Instances"]):
            if not isinstance(instance, dict):
                raise TypeError("Instances definition should be all objects/dict")
            if not keyisset("DBInstanceClass", instance):
                raise KeyError(
                    "You must specify at least the DBInstanceClass", instance.keys()
                )
            instance_props = import_record_properties(
                instance, docdb.DBInstance, ignore_missing_required=True
            )
            instance_props.update(
                {
                    "DBClusterIdentifier": Ref(db.cfn_resource),
                    "Tags": Tags(DocDbCluster=Ref(db.cfn_resource)),
                }
            )
            template.add_resource(
                docdb.DBInstance(f"{db.logical_name}Instance{count}", **instance_props)
            )


def create_docdb_template(root_template, new_resources, settings, self_stack):
    """
    Function to create the root template for DocDB and associate the new resources to it.

    :param troposphere.Template root_template:
    :param list new_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.docdb.docdb_stack.XStack self_stack:
    """
    for resource in new_resources:
        resource.stack = self_stack
        resource.db_subnets_group = docdb.DBSubnetGroup(
            f"{resource.logical_name}SubnetGroup",
            DBSubnetGroupDescription=Sub(
                f"docdb-{resource.logical_name}-subnets-${{{AWS_STACK_NAME}}}"
            ),
            SubnetIds=Ref(STORAGE_SUBNETS)
            if not resource.subnets_override
            else Ref(resource.subnets_override),
            Tags=Tags(Name=Sub(f"docdb-subnets-${{{AWS_STACK_NAME}}}")),
        )
        resource.db_sg = SecurityGroup(
            f"{resource.logical_name}Sg",
            GroupDescription=Sub(f"SG for docdb-{resource.logical_name}"),
            GroupName=Sub(f"${{{AWS_STACK_NAME}}}.docdb.{resource.logical_name}"),
            VpcId=Ref(VPC_ID),
        )
        root_template.add_resource(resource.db_subnets_group)
        root_template.add_resource(resource.db_sg)
        resource.db_secret = add_db_secret(root_template, resource.logical_name)
        set_db_cluster(
            root_template,
            resource,
            resource.db_secret,
            [GetAtt(resource.db_sg, "GroupId")],
        )
        attach_to_secret_to_resource(
            root_template, resource.cfn_resource, resource.db_secret
        )
        add_db_dependency(resource.cfn_resource, resource.db_secret)
        add_db_instances(root_template, resource)
        resource.init_outputs()
        resource.generate_outputs()
        root_template.add_output(resource.outputs)
