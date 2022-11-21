# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
RDS DB template generator
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .rds_stack import Rds
    from ecs_composex.common.settings import ComposeXSettings
    from troposphere import Template
    from boto3.session import Session

from compose_x_common.aws import get_session
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_NO_VALUE, GetAtt, If, NoValue, Ref, Sub, Tags
from troposphere.ec2 import SecurityGroup
from troposphere.rds import (
    DBCluster,
    DBClusterParameterGroup,
    DBInstance,
    DBParameterGroup,
    DBSubnetGroup,
)

from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.ecs_composex import TAGS_SEPARATOR
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_resource, build_template
from ecs_composex.rds import rds_conditions
from ecs_composex.rds.rds_parameter_groups_helper import (
    get_family_from_engine_version,
    get_family_settings,
)
from ecs_composex.rds.rds_params import (
    CLUSTER_PARAMETER_GROUP_T,
    DB_ENGINE_NAME,
    DB_ENGINE_VERSION,
    DB_INSTANCE_CLASS,
    DB_NAME,
    DB_PASSWORD_LENGTH,
    DB_SNAPSHOT_ID,
    DB_STORAGE_CAPACITY,
    DB_STORAGE_TYPE,
    DB_USERNAME,
    PARAMETER_GROUP_T,
)
from ecs_composex.resources_import import import_record_properties
from ecs_composex.secrets import (
    add_db_dependency,
    add_db_secret,
    attach_to_secret_to_resource,
)
from ecs_composex.vpc.vpc_params import (
    APP_SUBNETS,
    PUBLIC_SUBNETS,
    STORAGE_SUBNETS,
    VPC_ID,
)


def init_database_template(db: Rds) -> Template:
    """
    Initialize default DB Template
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
            APP_SUBNETS,
            PUBLIC_SUBNETS,
        ],
    )
    template.add_condition(
        rds_conditions.USE_DB_SNAPSHOT_CON_T, rds_conditions.USE_DB_SNAPSHOT_CON
    )
    template.add_condition(
        rds_conditions.NOT_USE_DB_SNAPSHOT_CON_T,
        rds_conditions.NOT_USE_DB_SNAPSHOT_CON,
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


def create_db_subnet_group(template: Template, db: Rds, subnets=None) -> DBSubnetGroup:
    """
    Create the DB Subnet Group
    """
    if not subnets:
        subnets = STORAGE_SUBNETS
    group = DBSubnetGroup(
        f"{db.logical_name}SubnetGroup",
        DBSubnetGroupDescription=Sub(
            f"DB Subnet group for {db.logical_name} in ${{AWS::StackName}}"
        ),
        SubnetIds=Ref(subnets),
        Tags=Tags(
            **{
                f"compose-x{TAGS_SEPARATOR}module": db.module.res_key,
                f"compose-x{TAGS_SEPARATOR}rds{TAGS_SEPARATOR}name": db.name,
                f"compose-x{TAGS_SEPARATOR}rds{TAGS_SEPARATOR}logical-name": db.logical_name,
            }
        ),
    )
    add_resource(template, group)
    return group


def add_db_sg(template, db):
    """
    Function to add a Security group for the database

    :param db: Name of the database as defined in compose file
    :param troposphere.Template template: template to add the sg to
    """
    sg = SecurityGroup(
        f"{db.logical_name}Sg",
        GroupName=Sub(
            f"${{STACK_NAME}}-{db.logical_name}", STACK_NAME=define_stack_name()
        ),
        GroupDescription=Sub(
            f"${{STACK_NAME}} {db.logical_name}", STACK_NAME=define_stack_name()
        ),
        VpcId=Ref(VPC_ID),
        Tags=Tags(
            **{
                f"compose-x{TAGS_SEPARATOR}module": db.module.res_key,
                f"compose-x{TAGS_SEPARATOR}rds{TAGS_SEPARATOR}name": db.name,
                f"compose-x{TAGS_SEPARATOR}rds{TAGS_SEPARATOR}logical-name": db.logical_name,
            }
        ),
    )
    add_resource(template, sg)
    return sg


def add_default_instance_definition(db: Rds, for_cluster: bool = False):
    """
    Add DB Instances
    """
    props = {
        "DBName": If(
            rds_conditions.USE_CLUSTER_OR_SNAPSHOT_CON_T, NoValue, Ref(DB_NAME)
        ),
        "Engine": Ref(DB_ENGINE_NAME),
        "EngineVersion": If(
            rds_conditions.USE_CLUSTER_CON_T,
            NoValue,
            Ref(DB_ENGINE_VERSION),
        ),
        "StorageType": If(
            rds_conditions.USE_CLUSTER_CON_T,
            Ref(AWS_NO_VALUE),
            Ref(DB_STORAGE_TYPE),
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
        props.update(
            {
                "DBClusterIdentifier": If(
                    rds_conditions.USE_CLUSTER_CON_T,
                    Ref(db.cfn_resource),
                    Ref(AWS_NO_VALUE),
                ),
            }
        )
        del props["StorageEncrypted"]

    instance = DBInstance(f"Instance{db.logical_name}", **props)
    return instance


def add_default_cluster_definition(db: Rds) -> DBCluster:
    """
    Imports definition and creates DBCluster resource
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
        "VpcSecurityGroupIds": [Ref(db.db_sg)],
        "Tags": Tags(SecretName=Ref(db.db_secret), Name=db.logical_name),
        "StorageEncrypted": True,
    }
    cluster = DBCluster(f"{db.logical_name}", **props)
    return cluster


def set_parameters_groups_from_macro_parameters(db: Rds, template: Template) -> None:
    """
    Set the DB parameters group if ParametersGroups is set on MacroParameters
    """
    if isinstance(db.cfn_resource, DBCluster):
        props = import_record_properties(
            db.parameters["ParametersGroups"], DBClusterParameterGroup
        )
        params = add_resource(
            template,
            DBClusterParameterGroup(
                CLUSTER_PARAMETER_GROUP_T,
                **props,
            ),
        )
        setattr(db.cfn_resource, "DBClusterParameterGroupName", Ref(params))
    elif isinstance(db.cfn_resource, DBInstance):
        props = import_record_properties(
            db.parameters["ParametersGroups"], DBParameterGroup
        )
        params = add_resource(
            template,
            DBParameterGroup(
                CLUSTER_PARAMETER_GROUP_T,
                **props,
            ),
        )
        setattr(db.cfn_resource, "DBParameterGroupName", Ref(params))


def validate_group_is_set(db: Rds) -> bool:
    if isinstance(db.cfn_resource, DBCluster) and hasattr(
        db.cfn_resource, "DBClusterParameterGroupName"
    ):
        _param = getattr(db.cfn_resource, "DBClusterParameterGroupName")
        if isinstance(_param, str) or isinstance(_param, Ref) and _param != NoValue:
            LOG.debug(
                f"{db.mod_res_key}.{db.name} - DBClusterParameterGroupName already set: {_param}"
            )
            return True

    elif isinstance(db.cfn_resource, DBInstance) and hasattr(
        db.cfn_resource, "DBParameterGroupName"
    ):
        _param = getattr(db.cfn_resource, "DBParameterGroupName")
        if isinstance(_param, str) or isinstance(_param, Ref) and _param != NoValue:
            LOG.debug(
                f"{db.mod_res_key}.{db.name} - DBParameterGroupName already set: {_param}"
            )
            return True
    return False


def define_parameters_group_from_engine_and_version(
    db: Rds,
    template: Template,
    engine_name: str,
    engine_version: str,
    session: Session = None,
) -> None:
    session = get_session(session)
    LOG.debug(
        f"{db.mod_res_key}.{db.name}"
        f" - Defining ParameterGroups based on default settings for {engine_name}@{engine_version}"
    )
    if not engine_name or not engine_version:
        raise KeyError(
            "Engine and EngineVersion must be set in either Properties or MacroParameters"
        )
    db_family = get_family_from_engine_version(engine_name, engine_version)
    if not db_family:
        raise LookupError(
            f"Failed to retrieve the DB Engine Family for {engine_name}@{engine_version}"
        )
    db_settings = get_family_settings(db_family, session)
    if isinstance(db.cfn_resource, DBInstance):
        params = add_resource(
            template,
            DBParameterGroup(
                PARAMETER_GROUP_T,
                Family=db_family,
                Parameters=db_settings,
                Description=f"copy from original for {db_family}",
            ),
        )
        setattr(db.cfn_resource, "DBParameterGroupName", Ref(params))
    elif isinstance(db.cfn_resource, DBCluster):
        params = add_resource(
            template,
            DBClusterParameterGroup(
                CLUSTER_PARAMETER_GROUP_T,
                Family=db_family,
                Parameters=db_settings,
                Description=f"copy from original for {db_family}",
            ),
        )
        setattr(db.cfn_resource, "DBClusterParameterGroupName", Ref(params))
    LOG.info(
        f"{db.mod_res_key}.{db.name} - "
        f"Defined Parameters groups from default for {engine_name}@{engine_version}"
    )


def add_parameter_group(template: Template, db: Rds, session: Session = None) -> None:
    """
    Create a DB ParameterGroup which uses the same values as default which can later be altered
    """
    if validate_group_is_set(db):
        LOG.debug(
            f"{db.mod_res_key}.{db.name} - ParameterGroupName set from Properties or MacroParameters"
        )
    elif db.parameters and keyisset("ParametersGroups", db.parameters):
        LOG.info(
            f"{db.mod_res_key}.{db.name} - Defining ParameterGroup from MacroParameters"
        )
        set_parameters_groups_from_macro_parameters(db, template)
    else:
        engine_name = set_else_none(
            DB_ENGINE_NAME.title,
            db.properties,
            alt_value=set_else_none(DB_ENGINE_NAME.title, db.parameters),
        )
        engine_version = set_else_none(
            DB_ENGINE_VERSION.title,
            db.properties,
            alt_value=set_else_none(DB_ENGINE_VERSION.title, db.parameters),
        )
        session = get_session(session)
        define_parameters_group_from_engine_and_version(
            db, template, engine_name, engine_version, session
        )


def override_set_properties(props: dict, db: Rds) -> None:
    """
    Override secrets parameters from the rds properties
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


def determine_resource_type(db_name: str, properties: dict) -> Union[type, None]:
    """
    Function to determine if the properties are the ones of a DB Cluster or DB Instance.
    Default assumes DBCluster if it can't make it out from properties.
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


def add_instances_from_parameters(db_template: Template, db: Rds) -> None:
    """
    Adds DB Instances based on the DB definition.
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


def create_from_properties(db_template: Template, db: Rds) -> None:
    """
    Function to create RDS resources based on the Properties defined in Compose files.
    It will try to identify what type of resource (Cluster or Instance) is defined based on the properties
    that were given. If not capable, falls back to using MacroParameters, and if not, raises exception
    """
    rds_class = determine_resource_type(db.name, db.properties)
    if rds_class:
        rds_props = import_record_properties(db.properties, rds_class)
        override_set_properties(rds_props, db)
        db.cfn_resource = rds_class(db.logical_name, **rds_props)
        add_resource(db_template, db.cfn_resource)
    elif db.parameters:
        create_from_parameters(db_template, db)
    else:
        raise RuntimeError(
            f"Failed to identify if {db.logical_name}"
            " is a Cluster or an Instance and MacroParameters are not set."
        )


def create_from_parameters(db_template: Template, db: Rds) -> None:
    """
    Function to create the RDS resources from MacroParameters when Properties are not set.
    """
    if db.parameters[DB_ENGINE_NAME.title].startswith("aurora"):
        db.cfn_resource = add_default_cluster_definition(db)
    else:
        db.cfn_resource = add_default_instance_definition(db)
    add_resource(db_template, db.cfn_resource)


def add_db_instances_for_cluster(db_template: Template, db: Rds) -> None:
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


def generate_database_template(db: Rds, settings: ComposeXSettings) -> Template:
    """
    Creates the database and its template. Will be used to create the stack for it.
    """
    db_template = init_database_template(db)
    db.db_secret = add_db_secret(db_template, db.logical_name)
    db.db_sg = add_db_sg(db_template, db)
    db.db_subnet_group = create_db_subnet_group(db_template, db)
    if db.properties:
        create_from_properties(db_template, db)
    elif not db.properties and db.parameters:
        create_from_parameters(db_template, db)
    if isinstance(db.cfn_resource, DBCluster):
        add_db_instances_for_cluster(db_template, db)
    add_parameter_group(db_template, db, session=settings.session)
    add_db_dependency(db.cfn_resource, db.db_secret)
    attach_to_secret_to_resource(db_template, db.cfn_resource, db.db_secret)
    db.init_outputs()
    return db_template
