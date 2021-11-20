#   -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re

from botocore.exceptions import ClientError
from compose_x_common.aws import get_assume_role_session
from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    AWS_STACK_NAME,
    AWS_URL_SUFFIX,
    FindInMap,
    GetAtt,
    Ref,
    Sub,
)
from troposphere.ecs import (
    CapacityProviderStrategyItem,
    Cluster,
    ClusterConfiguration,
    ExecuteCommandConfiguration,
    ExecuteCommandLogConfiguration,
)
from troposphere.logs import LogGroup

from ecs_composex.common import LOG
from ecs_composex.common.services_helpers import get_closest_valid_log_retention_period
from ecs_composex.ecs import metadata
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_T
from ecs_composex.kms.kms_stack import KmsKey
from ecs_composex.resources_import import import_record_properties
from ecs_composex.s3.s3_stack import Bucket
from ecs_composex.s3.s3_template import evaluate_parameters, generate_bucket

RES_KEY = "x-cluster"
FARGATE_PROVIDER = "FARGATE"
FARGATE_SPOT_PROVIDER = "FARGATE_SPOT"
DEFAULT_PROVIDERS = [FARGATE_PROVIDER, FARGATE_SPOT_PROVIDER]
DEFAULT_STRATEGY = [
    CapacityProviderStrategyItem(
        Weight=2, Base=1, CapacityProvider=FARGATE_SPOT_PROVIDER
    ),
    CapacityProviderStrategyItem(Weight=1, CapacityProvider=FARGATE_PROVIDER),
]


def get_kms_key_config(cluster_name, allow_kms_reuse=False):
    return


class EcsCluster(object):
    """
    Class to make it easier to manipulate the ECS Cluster to use and its various properties
    """

    mappings_key = "ecs"
    res_key = "x-cluster"

    def __init__(self, root_stack, definition=None, **kwargs):
        self.cfn_resource = None
        self.mappings = {}
        self.log_group = None
        self.log_bucket = None
        self.log_prefix = None
        self.log_key = None
        self.stack = None
        self.template = None
        self.platform_override = None
        self.capacity_providers = []
        self.default_strategy_providers = []
        self.cluster_identifier = Ref(AWS_STACK_NAME)
        if definition is None:
            self.set_default_cluster_config(root_stack)
            self.parameters = {}
            self.platform_override = None
        else:
            self.definition = definition
            self.use = (
                self.definition["Use"] if keyisset("Use", self.definition) else {}
            )
            self.lookup = (
                self.definition["Lookup"] if keyisset("Lookup", self.definition) else {}
            )
            self.properties = (
                self.definition["Properties"]
                if keyisset("Properties", self.definition)
                else {}
            )
            self.parameters = (
                self.definition["MacroParameters"]
                if keyisset("MacroParameters", self.definition)
                else {}
            )

    def set_from_definition(self, root_stack, session, settings):
        if self.definition and self.use:
            self.mappings = {CLUSTER_NAME.title: {"Name": self.use}}
            root_stack.stack_template.add_mapping(self.mappings_key, self.mappings)
            self.cluster_identifier = FindInMap(
                self.mappings_key, CLUSTER_NAME.title, "Name"
            )
        elif self.lookup:
            self.lookup_cluster(session)
            root_stack.stack_template.add_mapping(self.mappings_key, self.mappings)
        elif self.properties:
            self.define_cluster(root_stack, settings)

    def set_default_cluster_config(self, root_stack):
        """
        Function to get the default defined ECS Cluster configuration

        :return: cluster
        :rtype: troposphere.ecs.Cluster
        """
        self.log_group = LogGroup(
            "EcsExecLogGroup",
            LogGroupName=Sub(f"ecs/execute-logs/${{{AWS_STACK_NAME}}}"),
            RetentionInDays=120,
        )
        self.cfn_resource = Cluster(
            CLUSTER_T,
            ClusterName=Ref(AWS_STACK_NAME),
            CapacityProviders=DEFAULT_PROVIDERS,
            DefaultCapacityProviderStrategy=DEFAULT_STRATEGY,
            Configuration=ClusterConfiguration(
                ExecuteCommandConfiguration=ExecuteCommandConfiguration(
                    Logging="DEFAULT",
                    LogConfiguration=ExecuteCommandLogConfiguration(
                        CloudWatchLogGroupName=Ref(self.log_group),
                    ),
                )
            ),
            Metadata=metadata,
        )
        root_stack.stack_template.add_resource(self.log_group)
        root_stack.stack_template.add_resource(self.cfn_resource)
        self.capacity_providers = DEFAULT_PROVIDERS
        self.cluster_identifier = Ref(self.cfn_resource)

    def import_log_config(self, exec_config):
        """
        Sets the properties for bucket and cw log group to use for ECS Execute

        :param dict exec_config:
        :return:
        """
        if keyisset("logConfiguration", exec_config):
            log_config = exec_config["logConfiguration"]
            if keyisset("cloudWatchLogGroupName", log_config):
                self.mappings[CLUSTER_NAME.title][
                    "cloudWatchLogGroupName"
                ] = log_config["cloudWatchLogGroupName"]
                self.log_group = FindInMap(
                    self.mappings_key,
                    CLUSTER_NAME.title,
                    "cloudWatchLogGroupName",
                )
            if keyisset("s3BucketName", log_config):
                self.mappings[CLUSTER_NAME.title]["s3BucketName"] = log_config[
                    "s3BucketName"
                ]
                self.log_bucket = FindInMap(
                    self.mappings_key, CLUSTER_NAME.title, "s3BucketName"
                )

    def set_cluster_mappings(self, cluster_api_def):
        """
        From the API info on the cluster, evaluate whether config is needed to enable
        ECS Execution

        :param dict cluster_api_def:
        """
        if keyisset("configuration", cluster_api_def):
            config = cluster_api_def["configuration"]
            if keyisset("executeCommandConfiguration", config):
                exec_config = config["executeCommandConfiguration"]
                if keyisset("kmsKeyId", exec_config):
                    self.mappings[CLUSTER_NAME.title]["kmsKeyId"] = exec_config[
                        "kmsKeyId"
                    ]
                    self.log_key = FindInMap(
                        self.mappings_key, CLUSTER_NAME.title, "kmsKeyId"
                    )
                self.import_log_config(exec_config)

    def lookup_cluster(self, session):
        """
        Define the ECS Cluster properties and definitions from ECS API.

        :param boto3.session.Session session: Boto3 session to make API calls.
        :return: The cluster details
        :rtype: dict
        """
        if not isinstance(self.lookup, (str, dict)):
            raise TypeError(
                "The value for Lookup must be", str, dict, "Got", type(self.lookup)
            )
        client = session.client("ecs")
        if isinstance(self.lookup, dict):
            if keyisset("RoleArn", self.lookup):
                ecs_session = get_assume_role_session(
                    session,
                    self.lookup["RoleArn"],
                    session_name="EcsClusterLookup@ComposeX",
                )
                client = ecs_session.client("ecs")
            cluster_name = self.lookup["ClusterName"]
        else:
            cluster_name = self.lookup
        try:
            cluster_r = client.describe_clusters(
                clusters=[cluster_name],
                include=[
                    "SETTINGS",
                    "CONFIGURATIONS",
                    "ATTACHMENTS",
                    "TAGS",
                    "STATISTICS",
                ],
            )
            if not keyisset("clusters", cluster_r):
                LOG.warning(
                    f"No cluster named {cluster_name} found. Creating one with default settings"
                )
                return None
            elif (
                keyisset("clusters", cluster_r)
                and cluster_r["clusters"][0]["clusterName"] == cluster_name
            ):
                LOG.info(
                    f"Found ECS Cluster {cluster_name}. Setting {CLUSTER_NAME.title} accordingly."
                )
                the_cluster = cluster_r["clusters"][0]
                self.mappings = {
                    CLUSTER_NAME.title: {"Name": the_cluster["clusterName"]}
                }
                self.set_cluster_mappings(the_cluster)
                self.capacity_providers = evaluate_capacity_providers(the_cluster)
                if self.capacity_providers:
                    self.default_strategy_providers = get_default_capacity_strategy(
                        the_cluster
                    )
                self.platform_override = evaluate_fargate_is_set(
                    self.capacity_providers, the_cluster
                )

                self.cluster_identifier = FindInMap(
                    self.mappings_key, CLUSTER_NAME.title, "Name"
                )
        except ClientError as error:
            LOG.error(error)
            raise

    def set_kms_key(
        self, cluster_name, root_stack, settings, log_settings, log_configuration
    ):
        """
        Defines the KMS Key created to encrypt ECS Execute commands

        :param str cluster_name:
        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict log_settings:
        :param dict log_configuration:
        """
        action = [
            "kms:Encrypt*",
            "kms:Decrypt*",
            "kms:ReEncrypt*",
            "kms:GenerateDataKey*",
            "kms:Describe*",
        ]
        statement = [
            {
                "Sid": "Allow direct access to key metadata to the account",
                "Effect": "Allow",
                "Principal": {
                    "AWS": Sub(
                        f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:root"
                    )
                },
                "Action": ["kms:*"],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {"kms:CallerAccount": Ref(AWS_ACCOUNT_ID)}
                },
            },
            {
                "Sid": "Allows SSM to use the KMS key to encrypt/decrypt messages",
                "Effect": "Allow",
                "Principal": {"Service": Sub(f"ssm.${{{AWS_URL_SUFFIX}}}")},
                "Action": action,
                "Resource": "*",
            },
        ]
        if keyisset("CreateExecLoggingLogGroup", self.parameters):
            statement.append(
                {
                    "Sid": "Allow aws logs to encrypt decrypt messages",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": Sub(f"logs.${{{AWS_REGION}}}.${{{AWS_URL_SUFFIX}}}")
                    },
                    "Action": action,
                    "Resource": "*",
                    "Condition": {
                        "ArnLike": {
                            "kms:EncryptionContext:aws:logs:arn": Sub(
                                f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                "log-group:*"
                                if keyisset("AllowKmsKeyReuse", self.parameters)
                                else f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                f"log-group:/ecs/execute-logs/{cluster_name}"
                            )
                        }
                    },
                }
            )
        elif keyisset("AllowKmsKeyReuse", self.parameters):
            statement.append(
                {
                    "Sid": "Allow aws logs to encrypt decrypt messages",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": Sub(f"logs.${{{AWS_REGION}}}.${{{AWS_URL_SUFFIX}}}")
                    },
                    "Action": action,
                    "Resource": "*",
                    "Condition": {
                        "ArnLike": {
                            "kms:EncryptionContext:aws:logs:arn": Sub(
                                f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                "log-group:*"
                            )
                        }
                    },
                }
            )
        key_config = {
            "Properties": {
                "EnableKeyRotationg": True,
                "Enabled": True,
                "Description": Sub(
                    f"ECS Cluster {cluster_name} execute logging encryption key"
                ),
                "KeyPolicy": {
                    "Version": "2012-10-17",
                    "Id": "ecscluster-logging",
                    "Statement": statement,
                },
            },
            "Settings": {"Alias": Sub(f"alias/ecs/execute-logs/{cluster_name}")},
        }

        self.log_key = KmsKey(
            "ECSClusterLoggingKmsKey", key_config, "cluster", settings
        )
        self.log_key.stack = root_stack
        self.log_key.define_kms_key()
        root_stack.stack_template.add_resource(self.log_key.cfn_resource)
        log_settings["KmsKeyId"] = GetAtt(self.log_key.cfn_resource, "Arn")
        log_configuration["CloudWatchEncryptionEnabled"] = True

    def set_log_group(self, cluster_name, root_stack, log_configuration):
        self.log_group = LogGroup(
            "EcsExecLogGroup",
            LogGroupName=Sub(f"/ecs/execute-logs/{cluster_name}"),
            RetentionInDays=120
            if not keyisset("LogGroupRetentionInDays", self.parameters)
            else get_closest_valid_log_retention_period(
                self.parameters["LogGroupRetentionInDays"]
            ),
            KmsKeyId=GetAtt(self.log_key.cfn_resource, "Arn")
            if isinstance(self.log_key, KmsKey)
            else Ref(AWS_NO_VALUE),
            DependsOn=[self.log_key.cfn_resource.title]
            if isinstance(self.log_key, KmsKey)
            else [],
        )
        root_stack.stack_template.add_resource(self.log_group)
        log_configuration["CloudWatchLogGroupName"] = Ref(self.log_group)
        if isinstance(self.log_key, KmsKey):
            log_configuration["CloudWatchEncryptionEnabled"] = True

    def set_log_bucket(self, cluster_name, root_stack, settings, log_configuration):
        """
        Defines the S3 bucket and settings to log ECS Execution commands

        :param str cluster_name:
        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict log_configuration:
        :return:
        """
        bucket_config = {
            "Properties": {
                "AccessControl": "BucketOwnerFullControl",
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
            "MacroParameters": {
                "ExpandRegionToBucket": True,
                "ExpandAccountIdToBucket": True,
                "BucketPolicy": {
                    "PredefinedBucketPolicies": ["enforceSecureConnection"]
                },
            },
        }
        if isinstance(self.log_key, KmsKey):
            bucket_config["Properties"]["BucketEncryption"] = {
                "ServerSideEncryptionConfiguration": [
                    {
                        "BucketKeyEnabled": True,
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": GetAtt(self.log_key.cfn_resource, "Arn"),
                        },
                    }
                ]
            }
        self.log_bucket = Bucket(
            "ECSClusterLoggingBucket",
            bucket_config,
            "cluster",
            settings,
        )
        self.log_bucket.stack = root_stack
        generate_bucket(self.log_bucket)
        evaluate_parameters(self.log_bucket, root_stack.stack_template)
        root_stack.stack_template.add_resource(self.log_bucket.cfn_resource)
        log_configuration["S3BucketName"] = Ref(self.log_bucket.cfn_resource)
        log_configuration["S3KeyPrefix"] = Sub(f"ecs/execute-logs/{cluster_name}/")
        log_configuration["S3EncryptionEnabled"] = True

    def update_props_from_parameters(self, root_stack, settings):
        """
        Aadapt cluster config to settings

        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        cluster_name = (
            f"${{{AWS_STACK_NAME}}}"
            if isinstance(self.cfn_resource.ClusterName, (Ref, Sub, FindInMap))
            else self.cfn_resource.ClusterName
        )
        self.log_group = Ref(AWS_NO_VALUE)
        self.log_bucket = Ref(AWS_NO_VALUE)

        log_settings = {}
        log_configuration = {}
        if keyisset("CreateExecLoggingKmsKey", self.parameters):
            self.set_kms_key(
                cluster_name, root_stack, settings, log_settings, log_configuration
            )
        if keyisset("CreateExecLoggingLogGroup", self.parameters):
            self.set_log_group(cluster_name, root_stack, log_configuration)

        if keyisset("CreateExecLoggingBucket", self.parameters):
            self.set_log_bucket(cluster_name, root_stack, settings, log_configuration)

        log_settings["LogConfiguration"] = ExecuteCommandLogConfiguration(
            **log_configuration
        )
        log_settings["Logging"] = "OVERRIDE"
        configuration = ClusterConfiguration(
            ExecuteCommandConfiguration=ExecuteCommandConfiguration(**log_settings)
        )
        if not hasattr(self.cfn_resource, "Configuration"):
            setattr(self.cfn_resource, "Configuration", configuration)

    def define_cluster(self, root_stack, settings):
        """
        Function to create the cluster from provided properties.

        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        props = import_record_properties(self.properties, Cluster)
        props["Metadata"] = metadata
        if not keyisset("ClusterName", props):
            props["ClusterName"] = Ref(AWS_STACK_NAME)
        if keyisset("DefaultCapacityProviderStrategy", props) and not keyisset(
            "CapacityProviders", props
        ):
            raise KeyError(
                "When specifying DefaultCapacityProviderStrategy"
                " you must specify CapacityProviders"
            )
        self.cfn_resource = Cluster(CLUSTER_T, **props)
        root_stack.stack_template.add_resource(self.cfn_resource)
        if self.parameters:
            self.update_props_from_parameters(root_stack, settings)
        self.cluster_identifier = Ref(self.cfn_resource)


def evaluate_fargate_is_set(providers, cluster_def):
    """
    Evaluate if FARGATE or FARGATE_SPOT is defined in the cluster

    :param list[str] providers:
    :param dict cluster_def:
    :return: Whether FARGATE or FARGATE_SPOT is available
    :rtype: bool
    """

    fargate_present = FARGATE_PROVIDER in providers
    fargate_spot_present = FARGATE_SPOT_PROVIDER in providers
    if not fargate_present and not fargate_spot_present:
        LOG.warning(
            f"{cluster_def['clusterName']} - "
            f"No {FARGATE_PROVIDER} nor {FARGATE_SPOT_PROVIDER} listed in Capacity Providers."
            "Overriding to EC2 Launch Type"
        )
        return "EC2"
    return None


def evaluate_capacity_providers(cluster_def):
    """
    When using Looked'Up cluster, if there is no Fargate Capacity Provider, defined on cluster,
    rollback to EC2 mode.

    :param dict cluster_def:
    :return: List of capacity providers set on the ECS Cluster.
    :rtype: list
    """
    providers = []
    if keyisset("capacityProviders", cluster_def):
        providers = cluster_def["capacityProviders"]
    if not providers:
        LOG.warning(
            f"{cluster_def['clusterName']} - No capacityProvider defined. Fallback to ECS Default"
            "Overriding to EC2"
        )
    return providers


def get_default_capacity_strategy(cluster_def):
    strategy_providers = (
        [
            cap["capacityProvider"]
            for cap in cluster_def["defaultCapacityProviderStrategy"]
        ]
        if keyisset("defaultCapacityProviderStrategy", cluster_def)
        else []
    )
    return strategy_providers


def import_from_x_aws_cluster(compose_content):
    """
    Function to handle and override settings if x-aws-cluster is defined.

    :param compose_content:
    :return:
    """
    x_aws_key = "x-aws-cluster"
    if not keyisset(x_aws_key, compose_content):
        return
    if compose_content[x_aws_key].startswith("arn:aws"):
        cluster_name = re.sub(
            pattern=r"(arn:aws(?:-[a-z]+)?:ecs:[\S]+:[0-9]{12}:cluster/)",
            repl="",
            string=compose_content[x_aws_key],
        )
    else:
        cluster_name = compose_content[x_aws_key]
    compose_content[RES_KEY] = {"Use": cluster_name}


def add_ecs_cluster(root_stack, settings):
    """
    Function to create the ECS Cluster.

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if keyisset("x-aws-cluster", settings.compose_content):
        import_from_x_aws_cluster(settings.compose_content)
        LOG.info("x-aws-cluster was set. Overriding any defined x-cluster settings")
    if not keyisset(EcsCluster.res_key, settings.compose_content):
        LOG.info("No cluster information provided. Creating a new one")
        cluster = EcsCluster(root_stack)
    elif isinstance(settings.compose_content[RES_KEY], dict):
        cluster = EcsCluster(root_stack, settings.compose_content[EcsCluster.res_key])
        cluster.set_from_definition(root_stack, settings.session, settings)
    else:
        raise LookupError("Unable to determine what to do for x-cluster")
    settings.ecs_cluster = cluster
