# -*- coding: utf-8 -*-
"""
RDS DB template generator
"""

from troposphere import Sub, Ref, If
from troposphere.secretsmanager import (
    Secret,
    SecretTargetAttachment,
    GenerateSecretString,
)
from troposphere.rds import (
    DBSubnetGroup,
    DBCluster,
    DBClusterParameterGroup,
    DBInstance,
    DBParameterGroup,
    DBSecurityGroup,
    DBSecurityGroupIngress,
)
from troposphere.ec2 import SecurityGroup
from ecs_composex.common import LOG, build_template, cfn_conditions
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    VPC_ID_T,
    VPC_MAP_ID,
    VPC_MAP_ID_T,
    STORAGE_SUBNETS_T,
    STORAGE_SUBNETS,
)
from ecs_composex.vpc.vpc_conditions import (
    USE_VPC_MAP_ID_CON_T, USE_VPC_MAP_ID_CON,
    NOT_USE_VPC_MAP_ID_CON_T, NOT_USE_VPC_MAP_ID_CON
)
from ecs_composex.rds.rds_params import (
    DB_ENGINE_VERSION,
    DB_ENGINE_NAME,
    DBS_SUBNET_GROUP,
    DB_SG_T,
    DB_NAME,
    DB_NAME_T,
    DB_SNAPSHOT_ID,
    DB_INSTANCE_CLASS,
    DB_PASSWORD_LENGTH,
    DB_USERNAME_T,
    DB_USERNAME,
    DB_STORAGE_CAPACITY,
    DB_STORAGE_TYPE,
)
from ecs_composex.rds import rds_conditions
from ecs_composex.rds.rds_parameter_groups_helper import (
    get_family_from_engine_version,
    get_family_settings,
)

CLUSTER_SUBNET_GROUP = "ClusterSubnetGroup"
DB_SECRET_T = "RdsDbSecret"
CLUSTER_T = "AuroraCluster"
DATABASE_T = "RdsDatabase"
PARAMETER_GROUP_T = "RdsParametersGroup"
CLUSTER_PARAMETER_GROUP_T = "RdsClusterParameterGroup"


def create_db_subnet_group(template, conditional=False):
    """
    Function to add the subnet group to
    :param conditional: Whether or not the object should have a Condition for creation in CFN
    :type conditional: bool
    :return:
    :param template:

    :return: group, the DB Subnets Group
    :rtype: troposphere.rds.DBSubnetGroup
    """
    group = DBSubnetGroup(
        CLUSTER_SUBNET_GROUP,
        template=template,
        DBSubnetGroupName=If(
            cfn_conditions.USE_STACK_NAME_CON_T,
            Sub("db-subnet-group-${AWS::StackName}"),
            Sub(f"db-subnet-group-${{{ROOT_STACK_NAME_T}}}"),
        ),
        DBSubnetGroupDescription=If(
            cfn_conditions.USE_STACK_NAME_CON_T,
            Sub("DB Subnet group for ${AWS::StackName}"),
            Sub(f"DB Subnet group for ${{{ROOT_STACK_NAME_T}}}"),
        ),
        SubnetIds=Ref(STORAGE_SUBNETS),
    )
    if conditional:
        setattr(group, "Condition", rds_conditions.DBS_SUBNET_GROUP_CON_T)
    return group


def add_db_sg(template, db_name):
    """
    Function to add a Security group for the database
    :param db_name: Name of the database as defined in compose file
    :type db_name: str
    :param template: template to add the sg to
    :type template: troposphere.Template
    """
    SecurityGroup(
        DB_SG_T,
        template=template,
        GroupName=Sub(f"${{{ROOT_STACK_NAME_T}}}-${db_name}"),
        GroupDescription=Sub(f"${{{ROOT_STACK_NAME_T}}} ${db_name}"),
        VpcId=Ref(VPC_ID),
    )


def add_db_secret(template):
    """
    Function to add a Secrets Manager secret that will be associated with the DB
    :return:
    """
    Secret(
        DB_SECRET_T,
        template=template,
        GenerateSecretString=GenerateSecretString(
            SecretStringTemplate=Sub(f'{{"username":"${{{DB_USERNAME_T}}}"}}'),
            GenerateStringKey="password",
            ExcludeCharacters="<>%`|;,.",
            ExcludePunctuation=True,
            ExcludeLowercase=False,
            ExcludeUppercase=False,
            IncludeSpace=False,
            RequireEachIncludedType=True,
            PasswordLength=Ref(DB_PASSWORD_LENGTH),
        ),
    )
    SecretTargetAttachment(
        "ClusterRdsSecretAttachment",
        template=template,
        Condition=rds_conditions.USE_CLUSTER_CON_T,
        DependsOn=[DB_SECRET_T, CLUSTER_T],
        TargetType=DBCluster.resource_type,
        SecretId=Ref(DB_SECRET_T),
        TargetId=Ref(CLUSTER_T),
    )
    SecretTargetAttachment(
        "DatabaseRdsSecretAttachment",
        template=template,
        Condition=rds_conditions.NOT_USE_CLUSTER_CON_T,
        DependsOn=[DB_SECRET_T, DATABASE_T],
        TargetType=DBInstance.resource_type,
        SecretId=Ref(DB_SECRET_T),
        TargetId=Ref(DATABASE_T),
    )


def add_instance(template, db, **kwargs):
    """
    Function to add DB Instance(s)
    :param template:
    :param db:
    :param kwargs:
    :return:
    """
    db = DBInstance(
        DATABASE_T,
        template=template,
        Engine=Ref(DB_ENGINE_NAME),
        EngineVersion=Ref(DB_ENGINE_VERSION),
        StorageType=If(
            rds_conditions.USE_CLUSTER_CON_T, Ref("AWS::NoValue"), Ref(DB_STORAGE_TYPE)
        ),
        DBSubnetGroupName=If(
            rds_conditions.NOT_USE_CLUSTER_CON_T,
            If(
                rds_conditions.DBS_SUBNET_GROUP_CON_T,
                Ref(CLUSTER_SUBNET_GROUP),
                Ref(DBS_SUBNET_GROUP),
            ),
            Ref("AWS::NoValue"),
        ),
        AllocatedStorage=If(
            rds_conditions.USE_CLUSTER_CON_T,
            Ref("AWS::NoValue"),
            Ref(DB_STORAGE_CAPACITY),
        ),
        DBInstanceClass=Ref(DB_INSTANCE_CLASS),
        MasterUsername=If(
            rds_conditions.USE_CLUSTER_OR_SNAPSHOT_CON_T,
            Ref("AWS::NoValue"),
            Sub(
                f"{{{{resolve:secretsmanager:${{{DB_SECRET_T}}}:SecretString:username}}}}"
            ),
        ),
        DBClusterIdentifier=If(
            rds_conditions.USE_CLUSTER_CON_T, Ref(CLUSTER_T), Ref("AWS::NoValue")
        ),
        MasterUserPassword=If(
            rds_conditions.USE_CLUSTER_CON_T,
            Ref("AWS::NoValue"),
            Sub(
                f"{{{{resolve:secretsmanager:${{{DB_SECRET_T}}}:SecretString:password}}}}"
            ),
        ),
    )


def add_cluster(template, db, **kwargs):
    """
    Function to add the cluster to the template
    :param db:
    :param kwargs:
    :param template:
    :return:
    """
    cluster = DBCluster(
        CLUSTER_T,
        template=template,
        Condition=rds_conditions.USE_CLUSTER_CON_T,
        DBSubnetGroupName=If(
            rds_conditions.DBS_SUBNET_GROUP_CON_T,
            Ref(CLUSTER_SUBNET_GROUP),
            Ref(DBS_SUBNET_GROUP),
        ),
        DatabaseName=Ref(DB_NAME),
        MasterUsername=If(
            rds_conditions.USE_CLUSTER_AND_SNAPSHOT_CON_T,
            Ref("AWS::NoValue"),
            Sub(
                f"{{{{resolve:secretsmanager:${{{DB_SECRET_T}}}:SecretString:username}}}}"
            ),
        ),
        MasterUserPassword=Sub(
            f"{{{{resolve:secretsmanager:${{{DB_SECRET_T}}}:SecretString:password}}}}"
        ),
        SnapshotIdentifier=If(
            rds_conditions.USE_CLUSTER_CON_T,
            If(
                rds_conditions.USE_DB_SNAPSHOT_CON_T,
                Ref(DB_SNAPSHOT_ID),
                Ref("AWS::NoValue"),
            ),
            Ref("AWS::NoValue"),
        ),
        Engine=Ref(DB_ENGINE_NAME),
        EngineVersion=Ref(DB_ENGINE_VERSION),
        DBClusterParameterGroupName=Ref(CLUSTER_PARAMETER_GROUP_T),
    )
    return cluster


def add_parameter_group(template, db):
    """
    Function to create a parameter group which uses the same values as default which can later be altered

    :param template: the RDS template
    :param db: the db object as imported from Docker composeX file
    """
    db_family = get_family_from_engine_version(
        db["Properties"][DB_ENGINE_NAME.title],
        db["Properties"][DB_ENGINE_VERSION.title],
    )
    db_settings = get_family_settings(db_family)
    DBParameterGroup(
        PARAMETER_GROUP_T,
        template=template,
        Family=db_family,
        Parameters=db_settings,
        Condition=rds_conditions.NOT_USE_CLUSTER_CON_T,
    )
    DBClusterParameterGroup(
        CLUSTER_PARAMETER_GROUP_T,
        template=template,
        Condition=rds_conditions.USE_CLUSTER_CON_T,
        Family=db_family,
        Parameters=db_settings,
        Description=Sub(f"RDS Settings copy for {db_family}"),
    )


def init_database_template(db_name):
    """
    Function to initialize the DB Template
    :param db_name: Name of the DB as defined in compose file
    :type db_name: str

    :return: template
    :rtype: troposphere.Template
    """
    template = build_template(
        f"Template for RDS DB {db_name}",
        [
            VPC_ID,
            VPC_MAP_ID,
            DB_ENGINE_NAME,
            DB_ENGINE_VERSION,
            STORAGE_SUBNETS,
            DBS_SUBNET_GROUP,
            DB_NAME,
            DB_USERNAME,
            DB_SNAPSHOT_ID,
            DB_PASSWORD_LENGTH,
            DB_INSTANCE_CLASS,
            DB_STORAGE_CAPACITY,
            DB_STORAGE_TYPE,
        ],
    )
    template.add_condition(
        rds_conditions.DBS_SUBNET_GROUP_CON_T, rds_conditions.DBS_SUBNET_GROUP_CON
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
    template.add_condition(
        USE_VPC_MAP_ID_CON_T,
        USE_VPC_MAP_ID_CON
    )
    template.add_condition(
        NOT_USE_VPC_MAP_ID_CON_T,
        NOT_USE_VPC_MAP_ID_CON
    )
    create_db_subnet_group(template, True)
    return template


def generate_database_template(db_name, db, **kwargs):
    """
    Function to generate the database template
    :param db_name:
    :param db:
    :param kwargs:

    :return: db_template
    :rtype: troposphere.Template
    """
    db_template = init_database_template(db_name)
    add_cluster(db_template, db, **kwargs)
    add_db_secret(db_template)
    add_instance(db_template, None, **kwargs)
    add_parameter_group(db_template, db)
    return db_template
