# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

from botocore.exceptions import ClientError
from compose_x_common.aws import get_assume_role_session
from compose_x_common.aws.ecs import (
    CLUSTER_NAME_FROM_ARN,
    describe_all_ecs_clusters_from_ccapi,
    list_all_ecs_clusters,
)
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    AWS_STACK_NAME,
    AWS_URL_SUFFIX,
    FindInMap,
    GetAtt,
    NoValue,
    Ref,
    StackName,
    Sub,
)
from troposphere.ecs import (
    Cluster,
    ClusterConfiguration,
    ExecuteCommandConfiguration,
    ExecuteCommandLogConfiguration,
)
from troposphere.logs import LogGroup

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_resource, add_update_mapping
from ecs_composex.compose.compose_services.service_logging.helpers import (
    get_closest_valid_log_retention_period,
)
from ecs_composex.ecs import metadata
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_T
from ecs_composex.ecs_cluster.ecs_cluster_params import (
    DEFAULT_STRATEGY,
    FARGATE_PROVIDERS,
    RES_KEY,
)
from ecs_composex.ecs_cluster.helpers import (
    evaluate_capacity_providers,
    evaluate_fargate_is_set,
    get_default_capacity_strategy,
    import_from_x_aws_cluster,
)
from ecs_composex.kms.kms_stack import KmsKey
from ecs_composex.resources_import import import_record_properties

MANAGED_KMS_KEY_NAME = "ecs-cluster-logging-cmk"
MANAGED_S3_BUCKET_NAME = "ecs-cluster-logging-bucket"


def add_ecs_cluster(settings):
    """
    Function to create the ECS Cluster.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if keyisset("x-aws-cluster", settings.compose_content):
        import_from_x_aws_cluster(settings.compose_content)
        LOG.info("x-aws-cluster was set. Overriding any defined x-cluster settings")
    if not keyisset(EcsCluster.res_key, settings.compose_content):
        LOG.info("No cluster information provided. Creating a new one")
        cluster = EcsCluster(settings.root_stack)
    elif isinstance(settings.compose_content[RES_KEY], dict):
        cluster = EcsCluster(
            settings.root_stack, settings.compose_content[EcsCluster.res_key]
        )
        cluster.set_from_definition(settings.root_stack, settings.session, settings)
    else:
        raise LookupError("Unable to determine what to do for x-cluster")
    settings.ecs_cluster = cluster


def get_kms_key_config(cluster_name, allow_kms_reuse=False):
    return


class EcsCluster:
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
            self.lookup = set_else_none("Lookup", definition, alt_value={})
            if self.lookup:
                self.properties = {}
            else:
                self.properties = set_else_none("Properties", definition, alt_value={})
            self.parameters = set_else_none("MacroParameters", definition, alt_value={})

    def set_from_definition(self, root_stack, session, settings):
        if self.lookup:
            self.lookup_cluster(session)
            add_update_mapping(
                root_stack.stack_template, self.mappings_key, self.mappings
            )
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
            CapacityProviders=FARGATE_PROVIDERS,
            DefaultCapacityProviderStrategy=DEFAULT_STRATEGY,
            Configuration=ClusterConfiguration(
                ExecuteCommandConfiguration=ExecuteCommandConfiguration(
                    Logging="OVERRIDE",
                    LogConfiguration=ExecuteCommandLogConfiguration(
                        CloudWatchLogGroupName=Ref(self.log_group),
                    ),
                )
            ),
            Metadata=metadata,
        )
        add_resource(root_stack.stack_template, self.log_group)
        add_resource(root_stack.stack_template, self.cfn_resource)
        self.capacity_providers = FARGATE_PROVIDERS
        self.default_strategy_providers = [
            cap.CapacityProvider for cap in DEFAULT_STRATEGY
        ]
        self.cluster_identifier = Ref(self.cfn_resource)

    def import_log_config(self, exec_config):
        """
        Sets the properties for bucket and cw log group to use for ECS Execute

        :param dict exec_config:
        :return:
        """
        if keyisset("LogConfiguration", exec_config):
            log_config = exec_config["LogConfiguration"]
            if keyisset("CloudWatchLogGroupName", log_config):
                self.mappings[CLUSTER_NAME.title][
                    "CloudWatchLogGroupName"
                ] = log_config["CloudWatchLogGroupName"]
                self.log_group = FindInMap(
                    self.mappings_key,
                    CLUSTER_NAME.title,
                    "CloudWatchLogGroupName",
                )
            if keyisset("S3BucketName", log_config):
                self.mappings[CLUSTER_NAME.title]["S3BucketName"] = log_config[
                    "S3BucketName"
                ]
                self.log_bucket = FindInMap(
                    self.mappings_key, CLUSTER_NAME.title, "S3BucketName"
                )

    def set_cluster_mappings(self, cluster_api_def):
        """
        From the API info on the cluster, evaluate whether config is needed to enable
        ECS Execution

        :param dict cluster_api_def:
        """
        if keyisset("Configuration", cluster_api_def):
            config = cluster_api_def["Configuration"]
            if keyisset("ExecuteCommandConfiguration", config):
                exec_config = config["ExecuteCommandConfiguration"]
                if keyisset("KmsKeyId", exec_config):
                    self.mappings[CLUSTER_NAME.title]["KmsKeyId"] = exec_config[
                        "KmsKeyId"
                    ]
                    self.log_key = FindInMap(
                        self.mappings_key, CLUSTER_NAME.title, "KmsKeyId"
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
        ecs_session = session
        if isinstance(self.lookup, dict):
            if keyisset("RoleArn", self.lookup):
                ecs_session = get_assume_role_session(
                    session,
                    self.lookup["RoleArn"],
                    session_name="EcsClusterLookup@ComposeX",
                )
            cluster_name = self.lookup["ClusterName"]
        else:
            cluster_name = self.lookup
        try:
            clusters = list_all_ecs_clusters(session=ecs_session)
            cluster_names = [
                CLUSTER_NAME_FROM_ARN.match(c_name).group("name") for c_name in clusters
            ]
            clusters_config = describe_all_ecs_clusters_from_ccapi(
                clusters, return_as_map=True, use_cluster_name=True, session=ecs_session
            )
            if cluster_name not in clusters_config.keys():
                raise LookupError(
                    f"Failed to find {cluster_name}. Available clusters are",
                    cluster_names,
                )
            the_cluster = clusters_config[cluster_name]
            LOG.info(
                f"x-cluster.{cluster_name} found. Setting {CLUSTER_NAME.title} accordingly."
            )
            self.mappings = {CLUSTER_NAME.title: {"Name": the_cluster["ClusterName"]}}
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
        self,
        cluster_name,
        settings: ComposeXSettings,
        log_settings,
        log_configuration,
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
                            )
                            if keyisset("AllowKmsKeyReuse", self.parameters)
                            else Sub(
                                f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                "log-group:/ecs/execute-logs/${CLUSTER_NAME}*",
                                CLUSTER_NAME=cluster_name,
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
                "EnableKeyRotation": True,
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
            "Settings": {
                "Alias": Sub(
                    "alias/ecs/execute-logs/${CLUSTER_NAME}",
                    CLUSTER_NAME=cluster_name,
                )
            },
        }
        if not keyisset("x-kms", settings.compose_content):
            settings.compose_content["x-kms"] = {MANAGED_KMS_KEY_NAME: key_config}
        else:
            settings.compose_content["x-kms"][MANAGED_KMS_KEY_NAME] = key_config

        log_settings["KmsKeyId"] = f"x-kms::{MANAGED_KMS_KEY_NAME}"
        log_configuration["CloudWatchEncryptionEnabled"] = True

    def set_log_group(self, cluster_name, root_stack, log_configuration):
        self.log_group = LogGroup(
            "EcsExecLogGroup",
            LogGroupName=Sub(
                "/ecs/execute-logs/${CLUSTER_NAME}",
                CLUSTER_NAME=cluster_name,
            ),
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

    def set_log_bucket(
        self,
        cluster_name,
        settings: ComposeXSettings,
        log_configuration,
    ):
        """
        Defines the S3 bucket and settings to log ECS Execution commands

        :param str cluster_name:
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
        if keyisset("x-kms", settings.compose_content) and keyisset(
            "ecs-cluster-encryption-key", settings.compose_content["x-kms"]
        ):
            bucket_config["Properties"]["BucketEncryption"] = {
                "ServerSideEncryptionConfiguration": [
                    {
                        "BucketKeyEnabled": True,
                        "ServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": f"x-kms::{MANAGED_KMS_KEY_NAME}",
                        },
                    }
                ]
            }

        if not keyisset("x-s3", settings.compose_content):
            settings.compose_content["x-s3"] = {MANAGED_S3_BUCKET_NAME: bucket_config}
        else:
            settings.compose_content["x-s3"][MANAGED_S3_BUCKET_NAME] = bucket_config
        log_configuration["S3BucketName"] = f"x-s3::{MANAGED_S3_BUCKET_NAME}"
        log_configuration["S3KeyPrefix"] = Sub(
            "ecs/execute-logs/${CLUSTER_NAME}/", CLUSTER_NAME=cluster_name
        )
        log_configuration["S3EncryptionEnabled"] = True

    def update_props_from_parameters(
        self, cluster_name, root_stack, settings: ComposeXSettings
    ):
        """
        Adapt cluster config to settings
        """
        cluster_name = StackName if cluster_name == NoValue else cluster_name
        self.log_group = Ref(AWS_NO_VALUE)
        self.log_bucket = Ref(AWS_NO_VALUE)

        log_settings = {}
        log_configuration = {}
        if keyisset("CreateExecLoggingKmsKey", self.parameters):
            self.set_kms_key(
                cluster_name,
                settings,
                log_settings,
                log_configuration,
            )
        if keyisset("CreateExecLoggingLogGroup", self.parameters):
            self.set_log_group(cluster_name, root_stack, log_configuration)

        if keyisset("CreateExecLoggingBucket", self.parameters):
            self.set_log_bucket(cluster_name, settings, log_configuration)

        log_settings["LogConfiguration"] = ExecuteCommandLogConfiguration(
            **log_configuration
        )
        log_settings["Logging"] = "OVERRIDE"
        configuration = ClusterConfiguration(
            ExecuteCommandConfiguration=ExecuteCommandConfiguration(**log_settings)
        )
        return configuration

    def define_cluster(self, root_stack, settings: ComposeXSettings):
        """
        Function to create the cluster from provided properties.
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
        cluster_name = props["ClusterName"]
        if self.parameters:
            configuration = self.update_props_from_parameters(
                cluster_name, root_stack, settings
            )
            props["Configuration"] = configuration
        self.cfn_resource = Cluster(CLUSTER_T, **props)
        root_stack.stack_template.add_resource(self.cfn_resource)
        self.cluster_identifier = Ref(self.cfn_resource)
