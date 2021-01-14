# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
RDS DB template generator
"""

from troposphere import Sub, Ref, GetAtt, If, Tags, AWS_NO_VALUE
from troposphere.ec2 import SecurityGroup
from troposphere.rds import (
    DBSubnetGroup,
    DBCluster,
    DBClusterParameterGroup,
    DBInstance,
    DBParameterGroup,
)

from ecs_composex.common import (
    build_template,
    cfn_conditions,
    keyisset,
    LOG,
)
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.rds import rds_conditions
from ecs_composex.rds.rds_parameter_groups_helper import (
    get_family_from_engine_version,
    get_family_settings,
)
from ecs_composex.rds.rds_params import (
    CLUSTER_SUBNET_GROUP,
    PARAMETER_GROUP_T,
    CLUSTER_PARAMETER_GROUP_T,
)
from ecs_composex.rds.rds_params import (
    DB_ENGINE_VERSION,
    DB_ENGINE_NAME,
    DB_NAME,
    DB_SNAPSHOT_ID,
    DB_INSTANCE_CLASS,
    DB_PASSWORD_LENGTH,
    DB_USERNAME,
    DB_STORAGE_CAPACITY,
    DB_STORAGE_TYPE,
)
from ecs_composex.resources_import import import_record_properties
from ecs_composex.secrets import (
    add_db_secret,
    add_db_dependency,
    attach_to_secret_to_resource,
)
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    STORAGE_SUBNETS,
)


def init_database_template(db):
    """
    Function to initialize the DB Template

    :param db: The DB definition
    :return: template
    :rtype: troposphere.Template
    """
    template = build_template(
        f"Template for RDS DB {db.name}",
        [
            VPC_ID,
            DB_ENGINE_NAME,
            DB_ENGINE_VERSION,
            DB_NAME,
            DB_USERNAME,
            DB_SNAPSHOT_ID,
            DB_PASSWORD_LENGTH,
            DB_INSTANCE_CLASS,
            DB_STORAGE_CAPACITY,
            DB_STORAGE_TYPE,
            STORAGE_SUBNETS,
        ],
    )
    template.add_condition(
        rds_conditions.USE_DB_SNAPSHOT_CON_T, rds_conditions.USE_DB_SNAPSHOT_CON
    )
    template.add_condition(
        rds_conditions.NOT_USE_DB_SNAPSHOT_CON_T, rds_conditions.NOT_USE_DB_SNAPSHOT_CON
    )
    template.add_condition(
        rds_conditions.USE_CLUSTER_CON_T, rds_conditions.USE_CLUSTER_CON
    )
    template.add_condition(
        rds_conditions.NOT_USE_CLUSTER_CON_T, rds_conditions.NOT_USE_CLUSTER_CON
    )
    template.add_condition(
        rds_conditions.USE_CLUSTER_AND_SNAPSHOT_CON_T,
        rds_conditions.USE_CLUSTER_AND_SNAPSHOT_CON,
    )
    template.add_condition(
        rds_conditions.USE_CLUSTER_NOT_SNAPSHOT_CON_T,
        rds_conditions.USE_CLUSTER_NOT_SNAPSHOT_CON,
    )
    template.add_condition(
        rds_conditions.NOT_USE_CLUSTER_USE_SNAPSHOT_CON_T,
        rds_conditions.NOT_USE_CLUSTER_USE_SNAPSHOT_CON,
    )
    template.add_condition(
        rds_conditions.USE_CLUSTER_OR_SNAPSHOT_CON_T,
        rds_conditions.USE_CLUSTER_OR_SNAPSHOT_CON,
    )
    return template


def add_db_outputs(db_template, db):
    """
    Function to add outputs to the DB template

    :param troposphere.Template db_template: DB Template
    :param ecs_composex.rds.rds_stack.Rds db:
    """
    db.generate_outputs()
    db_template.add_output(db.outputs)


def create_db_subnet_group(template, db, subnets=None):
    """
    Function to create a subnet group

    :param troposphere.Template template: the template to add the subnet group to.
    :param bool conditional: Whether or not the object should have a Condition for creation in CFN
    :param subnets: The subnets to use.
    :return: group, the DB Subnets Group
    :rtype: troposphere.rds.DBSubnetGroup
    """
    if not subnets:
        subnets = STORAGE_SUBNETS
    group = DBSubnetGroup(
        f"{db.logical_name}SubnetGroup",
        template=template,
        DBSubnetGroupDescription=Sub(
            f"DB Subnet group for {db.logical_name} in ${{AWS::StackName}}"
        ),
        SubnetIds=Ref(subnets),
    )
    return group


def add_db_sg(template, db_name):
    """
    Function to add a Security group for the database

    :param str db_name: Name of the database as defined in compose file
    :param troposphere.Template template: template to add the sg to
    """
    return SecurityGroup(
        f"{db_name}Sg",
        template=template,
        GroupName=Sub(f"${{{ROOT_STACK_NAME_T}}}-{db_name}"),
        GroupDescription=Sub(f"${{{ROOT_STACK_NAME_T}}} ${db_name}"),
        VpcId=Ref(VPC_ID),
    )


def add_default_instance_definition(db, for_cluster=False):
    """
    Function to add DB Instance(s)

    :param ecs_composex.rds.rds_stack.Rds db:
    :param bool for_cluster: Whether this instance is added with default values for a DB Cluster
    """
    props = {
        "Engine": Ref(DB_ENGINE_NAME),
        "EngineVersion": Ref(DB_ENGINE_VERSION),
        "StorageType": If(
            rds_conditions.USE_CLUSTER_CON_T, Ref(AWS_NO_VALUE), Ref(DB_STORAGE_TYPE)
        ),
        "DBSubnetGroupName": If(
            rds_conditions.NOT_USE_CLUSTER_CON_T,
            Ref(db.db_subnet_group),
            Ref(AWS_NO_VALUE),
        ),
        "AllocatedStorage": If(
            rds_conditions.USE_CLUSTER_CON_T,
            Ref(AWS_NO_VALUE),
            Ref(DB_STORAGE_CAPACITY),
        ),
        "DBInstanceClass": Ref(DB_INSTANCE_CLASS),
        "MasterUsername": If(
            rds_conditions.USE_CLUSTER_OR_SNAPSHOT_CON_T,
            Ref(AWS_NO_VALUE),
            Sub(
                f"{{{{resolve:secretsmanager:${{{db.db_secret.title}}}:SecretString:username}}}}"
            ),
        ),
        "DBClusterIdentifier": If(
            rds_conditions.USE_CLUSTER_CON_T, Ref(db.cfn_resource), Ref(AWS_NO_VALUE)
        ),
        "MasterUserPassword": If(
            rds_conditions.USE_CLUSTER_CON_T,
            Ref(AWS_NO_VALUE),
            Sub(
                f"{{{{resolve:secretsmanager:${{{db.db_secret.title}}}:SecretString:password}}}}"
            ),
        ),
        "VPCSecurityGroups": If(
            rds_conditions.USE_CLUSTER_CON_T,
            Ref(AWS_NO_VALUE),
            [GetAtt(db.db_sg, "GroupId")],
        ),
        "Tags": Tags(SecretName=Ref(db.db_secret), Name=db.logical_name),
        "StorageEncrypted": True,
    }
    if db.parameters and keyisset("MultiAZ", db.parameters):
        props["MultiAZ"] = True
    if for_cluster and keyisset("StorageEncrypted", props):
        del props["StorageEncrypted"]

    instance = DBInstance(f"Instance{db.logical_name}", **props)
    return instance


def add_default_cluster_definition(db):
    """
    Function to add the cluster to the template

    :param ecs_composex.rds.rds_stack.Rds db: The Rds resource
    :return: cluster
    :rtype: troposphere.rds.DBCluster
    """
    props = {
        "Condition": rds_conditions.USE_CLUSTER_CON_T,
        "DBSubnetGroupName": Ref(db.db_subnet_group),
        "DatabaseName": Ref(DB_NAME),
        "MasterUsername": If(
            rds_conditions.USE_CLUSTER_AND_SNAPSHOT_CON_T,
            Ref(AWS_NO_VALUE),
            Sub(
                f"{{{{resolve:secretsmanager:${{{db.db_secret.title}}}:SecretString:username}}}}"
            ),
        ),
        "MasterUserPassword": Sub(
            f"{{{{resolve:secretsmanager:${{{db.db_secret.title}}}:SecretString:password}}}}"
        ),
        "SnapshotIdentifier": If(
            rds_conditions.USE_CLUSTER_CON_T,
            If(
                rds_conditions.USE_DB_SNAPSHOT_CON_T,
                Ref(DB_SNAPSHOT_ID),
                Ref(AWS_NO_VALUE),
            ),
            Ref(AWS_NO_VALUE),
        ),
        "Engine": Ref(DB_ENGINE_NAME),
        "EngineVersion": Ref(DB_ENGINE_VERSION),
        "DBClusterParameterGroupName": Ref(CLUSTER_PARAMETER_GROUP_T),
        "VpcSecurityGroupIds": [Ref(db.db_sg)],
        "Tags": Tags(SecretName=Ref(db.db_secret), Name=db.logical_name),
        "StorageEncrypted": True,
    }
    cluster = DBCluster(f"Cluster{db.logical_name}", **props)
    return cluster


def add_parameter_group(template, db):
    """
    Function to create a parameter group which uses the same values as default which can later be altered

    :param troposphere.Template template: the RDS template
    :param db: the db object as imported from Docker composeX file
    :type db: ecs_composex.common.compose_resources.Rds
    """

    if db.parameters and keyisset("ParametersGroups", db.parameters):
        if isinstance(db.cfn_resource, DBCluster):
            props = import_record_properties(
                db.parameters["ParametersGroups"], DBClusterParameterGroup
            )
            template.add_resource(
                DBClusterParameterGroup(
                    CLUSTER_PARAMETER_GROUP_T,
                    **props,
                )
            )
            return
        elif isinstance(db.cfn_resource, DBInstance):
            props = import_record_properties(
                db.parameters["ParametersGroups"], DBParameterGroup
            )
            template.add_resource(
                DBParameterGroup(
                    CLUSTER_PARAMETER_GROUP_T,
                    **props,
                )
            )

    if db.properties and not db.parameters:
        db_family = get_family_from_engine_version(
            db.properties[DB_ENGINE_NAME.title],
            db.properties[DB_ENGINE_VERSION.title],
        )
    elif (
        not db.properties
        and db.parameters
        and not keyisset("ParametersGroups", db.parameters)
    ):
        db_family = get_family_from_engine_version(
            db.parameters[DB_ENGINE_NAME.title],
            db.parameters[DB_ENGINE_VERSION.title],
        )
    else:
        raise RuntimeError("Failed to determine the DB Parameters family.", db.name)
    if not db_family:
        raise ValueError(
            "Failed to retrieve the DB Family for "
            f"{db.proparametersperties['DB_ENGINE_NAME.title']}"
            f"{db.parameters['DB_ENGINE_VERSION.title']}"
        )
    db_settings = get_family_settings(db_family)
    if isinstance(db.cfn_resource, DBInstance):
        DBParameterGroup(
            PARAMETER_GROUP_T,
            template=template,
            Family=db_family,
            Parameters=db_settings,
        )
    elif isinstance(db.cfn_resource, DBCluster):
        DBClusterParameterGroup(
            CLUSTER_PARAMETER_GROUP_T,
            template=template,
            Family=db_family,
            Parameters=db_settings,
            Description=Sub(f"RDS Settings copy for {db_family}"),
        )


def override_set_properties(props, db):
    """
    Function to override secrets parameters from the rds properties
    """
    props.update(
        {
            "MasterUsername": If(
                rds_conditions.USE_CLUSTER_AND_SNAPSHOT_CON_T,
                Ref(AWS_NO_VALUE),
                Sub(
                    f"{{{{resolve:secretsmanager:${{{db.db_secret.title}}}:SecretString:username}}}}"
                ),
            ),
            "MasterUserPassword": Sub(
                f"{{{{resolve:secretsmanager:${{{db.db_secret.title}}}:SecretString:password}}}}"
            ),
            "VpcSecurityGroupIds": [Ref(db.db_sg)],
            "DBSubnetGroupName": Ref(db.db_subnet_group),
        },
    )


def determine_resource_type(db_name, properties):
    """
    Function to determine if the properties are the ones of a DB Cluster or DB Instance.
    By default it will assume Cluster if cannot conclude that it is a DB Instance

    :param str db_name:
    :param dict properties:
    :return:
    """
    if (
        keyisset(DB_ENGINE_NAME.title, properties)
        and properties[DB_ENGINE_NAME.title].startswith("aurora")
        or all(
            property_name in DBCluster.props.keys()
            for property_name in properties.keys()
        )
    ):
        LOG.info(f"Identified {db_name} to be a RDS Aurora Cluster")
        return DBCluster
    elif all(
        property_name in DBInstance.props.keys() for property_name in properties.keys()
    ):
        LOG.info(f"Identified {db_name} to be a RDS Instance")
        return DBInstance
    LOG.error(
        "From the properties defined, we cannot determine whether this is a RDS Cluster or RDS Instance."
        " Setting to Cluster"
    )
    return None


def add_instances_from_parameters(db_template, db):
    """
    Function to go over each Instance defined in parameters

    :param troposphere.Template db_template: The template to add the resources to.
    :param ecs_composex.rds.rds_stack.Rds db: The Db object defined in compose.
    :raises: TypeError
    """
    aurora_compatible = [
        "Engine",
        "UseDefaultProcessorFeatures",
        "Tags",
        "SourceRegion",
        "SourceDBInstanceIdentifier",
        "PubliclyAccessible",
        "PromotionTier",
        "ProcessorFeatures",
        "PreferredMaintenanceWindow",
        "EnablePerformanceInsights",
        "AllowMajorVersionUpgrade",
        "AssociatedRoles",
        "CACertificateIdentifier",
        "DBInstanceClass",
        "DBParameterGroupName",
    ]
    if not isinstance(db.parameters["Instances"], list):
        raise TypeError("The Instances in MacroParameters must be a list of dict")
    for count, db_instance in enumerate(db.parameters["Instances"]):
        if not isinstance(db_instance, dict):
            raise TypeError(
                "The instance defined must be the CFN properties for RDS Instance. Got",
                type(db_instance),
            )
        instance_props = import_record_properties(db_instance, DBInstance)
        instance_props["Engine"] = Ref(DB_ENGINE_NAME)

        to_del = [
            prop_name
            for prop_name in instance_props.keys()
            if prop_name not in aurora_compatible
        ]
        for key in to_del:
            del instance_props[key]
        db_instance = DBInstance(
            f"{db.logical_name}Instance{count}",
            DBClusterIdentifier=Ref(db.cfn_resource),
            **instance_props,
        )
        db_template.add_resource(db_instance)


def create_from_properties(db_template, db):
    """
    Function to create RDS resources based on the Properties defined in Compose files.
    It will try to identify what type of resource (Cluster or Instance) is defined based on the properties
    that were given. If not capable, falls back to using MacroParameters, and if not, raises exception

    :param troposphere.Template db_template: The template to add the resources to.
    :param ecs_composex.rds.rds_stack.Rds db: The Db object defined in compose.
    :raises: RuntimeError
    """
    rds_class = determine_resource_type(db.name, db.properties)
    if rds_class:
        rds_props = import_record_properties(db.properties, rds_class)
        override_set_properties(rds_props, db)
        db.cfn_resource = rds_class(db.logical_name, **rds_props)
        db_template.add_resource(db.cfn_resource)
    elif db.parameters:
        create_from_parameters(db_template, db)
    else:
        raise RuntimeError(
            f"Failed to identify if {db.logical_name}"
            " is a Cluster or an Instance and MacroParameters are not set."
        )


def create_from_parameters(db_template, db):
    """
    Function to create the RDS resources from MacroParameters when Properties are not set.

    :param troposphere.Template db_template:
    :param ecs_composex.rds.rds_stack.Rds db:
    :return:
    """
    if db.parameters[DB_ENGINE_NAME.title].startswith("aurora"):
        db.cfn_resource = add_default_cluster_definition(db)
    else:
        db.cfn_resource = add_default_instance_definition(db)
    db_template.add_resource(db.cfn_resource)


def add_db_instances_for_cluster(db_template, db):
    """
    Function to add DB instances for a RDS Cluster

    :param troposphere.Template db_template:
    :param ecs_composex.rds.rds_stack.Rds db:
    """
    if not db.parameters or (
        db.parameters and not keyisset("Instances", db.parameters)
    ):
        db_instance = add_default_instance_definition(db, for_cluster=True)
        db_template.add_resource(db_instance)
    elif db.parameters and keyisset("Instances", db.parameters):
        add_instances_from_parameters(db_template, db)


def generate_database_template(db):
    """
    Function to generate the database template
    :param ecs_composex.rds.rds_stack.Rds db: The database object

    :return: db_template
    :rtype: troposphere.Template
    """
    db_template = init_database_template(db)
    db.db_secret = add_db_secret(db_template, db.logical_name)
    db.db_sg = add_db_sg(db_template, db.logical_name)
    db.db_subnet_group = create_db_subnet_group(db_template, db)
    if db.properties:
        create_from_properties(db_template, db)
    elif not db.properties and db.parameters:
        create_from_parameters(db_template, db)
    if isinstance(db.cfn_resource, DBCluster):
        add_db_instances_for_cluster(db_template, db)
    add_parameter_group(db_template, db)
    add_db_dependency(db.cfn_resource, db.db_secret)
    attach_to_secret_to_resource(db_template, db.cfn_resource, db.db_secret)
    db.init_outputs()
    add_db_outputs(db_template, db)
    db.is_nested = True
    return db_template
