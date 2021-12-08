#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to control S3 stack
"""

import json

from boto3.session import Session
from botocore.exceptions import ClientError
from compose_x_common.aws import get_account_id
from compose_x_common.aws.kms import (
    KMS_ALIAS_ARN_RE,
    KMS_KEY_ARN_RE,
    get_key_from_alias,
)
from compose_x_common.aws.s3 import S3_BUCKET_ARN_RE
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import MAX_OUTPUTS, GetAtt, Ref
from troposphere.s3 import Bucket as CfnBucket

from ecs_composex.common import build_template, setup_logging
from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.s3.s3_params import (
    CONTROL_CLOUD_ATTR_MAPPING,
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
    S3_BUCKET_ARN,
    S3_BUCKET_DOMAIN_NAME,
    S3_BUCKET_KMS_KEY,
    S3_BUCKET_NAME,
)
from ecs_composex.s3.s3_template import evaluate_parameters, generate_bucket

COMPOSEX_MAX_OUTPUTS = MAX_OUTPUTS - 10
LOG = setup_logging()


def create_s3_template(new_buckets, template):
    """
    Function to create the root S3 template.

    :param list new_buckets:
    :param troposphere.Template template:
    :return:
    """
    mono_template = False
    if len(list(new_buckets)) <= COMPOSEX_MAX_OUTPUTS:
        mono_template = True

    for bucket in new_buckets:
        generate_bucket(bucket)
        if bucket.cfn_resource:
            bucket.init_outputs()
            bucket.generate_outputs()
            bucket_template = template
            if mono_template:
                bucket_template.add_resource(bucket.cfn_resource)
                bucket_template.add_output(bucket.outputs)
            elif not mono_template:
                bucket_template = build_template(
                    f"Template for S3 Bucket {bucket.title}"
                )
                bucket_template.add_resource(bucket.cfn_resource)
                bucket_template.add_output(bucket.outputs)
                bucket_stack = ComposeXStack(
                    bucket.logical_name, stack_template=bucket_template
                )
                template.add_resource(bucket_stack)
            evaluate_parameters(bucket, bucket_template)
    return template


def validate_bucket_kms_key(kms_key, lookup_session):
    """
    Function to evaluate the KMS Key ID and ensure we return a KMS Key ARN

    :param str kms_key:
    :param boto3.session.Session lookup_session: Settings session
    :return: The KMS Key ARN or None
    :rtype: str
    """
    if KMS_KEY_ARN_RE.match(kms_key):
        return kms_key
    elif KMS_ALIAS_ARN_RE.match(kms_key):
        key_alias = KMS_ALIAS_ARN_RE.match(kms_key).group("key_alias")
        key = get_key_from_alias(key_alias, session=lookup_session)
        if key and keyisset("KeyArn", key):
            return key["KeyArn"]
    elif kms_key == "aws/s3":
        LOG.warn("KMS Key used the aws/s3 default key.")
        key = get_key_from_alias("alias/aws/s3", session=lookup_session)
        if key and keyisset("KeyArn", key):
            return key["KeyArn"]
    return None


def get_bucket_kms_key_from_config(bucket, bucket_config, session):
    """
    Function to get the KMS Encryption key if defined.

    :param ecs_composex.s3.s3_stack.Bucket bucket:
    :param dict bucket_config:
    :param boto3.session.Session session: Settings session
    :return: The KMS Key ARN or None
    :rtype: str
    """
    rules = (
        []
        if not (
            keyisset("ServerSideEncryptionConfiguration", bucket_config)
            and keyisset("Rules", bucket_config["ServerSideEncryptionConfiguration"])
        )
        else bucket_config["ServerSideEncryptionConfiguration"]["Rules"]
    )
    for rule in rules:
        if keyisset("ApplyServerSideEncryptionByDefault", rule):
            settings = rule["ApplyServerSideEncryptionByDefault"]
            if (
                keyisset("SSEAlgorithm", settings)
                and settings["SSEAlgorithm"] == "aws:kms"
                and keyisset("KMSMasterKeyID", settings)
            ):
                return validate_bucket_kms_key(settings["KMSMasterKeyID"], session)
    return None


def get_bucket_config(bucket, resource_id):
    """

    :param Bucket bucket:
    :return:
    """
    bucket_config = {
        S3_BUCKET_NAME.title: resource_id,
        S3_BUCKET_ARN.return_value: bucket.arn,
    }
    client = bucket.lookup_session.client("s3")

    try:
        encryption_r = client.get_bucket_encryption(Bucket=resource_id)
        encryption_attributes = attributes_to_mapping(
            encryption_r, CONTROL_CLOUD_ATTR_MAPPING
        )
        if keyisset(
            CONTROL_CLOUD_ATTR_MAPPING[S3_BUCKET_KMS_KEY.return_value],
            encryption_attributes,
        ):
            bucket_config[S3_BUCKET_KMS_KEY.return_value] = encryption_attributes[
                S3_BUCKET_KMS_KEY.return_value
            ]

    except ClientError as error:
        if (
            not error.response["Error"]["Code"]
            == "ServerSideEncryptionConfigurationNotFoundError"
        ):
            raise
        LOG.warning(error.response["Error"]["Message"])
    return bucket_config


class Bucket(XResource):
    """
    Class for S3 bucket.
    """

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        self.cloud_control_attributes_mapping = CONTROL_CLOUD_ATTR_MAPPING

    def init_outputs(self):
        self.output_properties = {
            S3_BUCKET_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            S3_BUCKET_ARN: (
                f"{self.logical_name}{S3_BUCKET_ARN.title}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_ARN.return_value,
            ),
            S3_BUCKET_DOMAIN_NAME: (
                f"{self.logical_name}{S3_BUCKET_DOMAIN_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_DOMAIN_NAME.return_value,
                None,
            ),
        }

    def native_attributes_mapping_lookup(self, account_id, resource_id, function):
        properties = function(self, resource_id)
        if self.native_attributes_mapping:
            conform_mapping = attributes_to_mapping(
                properties, self.native_attributes_mapping
            )
            return conform_mapping
        return properties

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
        if keyisset("Arn", self.lookup):
            arn_parts = arn_re.match(self.lookup["Arn"])
            if not arn_parts:
                raise KeyError(
                    f"{self.module_name}.{self.name} - ARN {self.lookup['Arn']} is not valid. Must match",
                    arn_re.pattern,
                )
            self.arn = self.lookup["Arn"]
            resource_id = arn_parts.group("id")
        elif keyisset("Tags", self.lookup):
            self.arn = find_aws_resource_arn_from_tags_api(
                self.lookup, self.lookup_session, tagging_api_id
            )
            arn_parts = arn_re.match(self.arn)
            resource_id = arn_parts.group("id")
        else:
            raise KeyError(
                f"{self.module_name}.{self.name} - You must specify Arn or Tags to identify existing resource"
            )
        if not self.arn:
            raise LookupError(
                f"{self.module_name}.{self.name} - Failed to find the AWS Resource with given tags"
            )
        props = {}
        if self.cloud_control_attributes_mapping:
            _s3 = self.lookup_session.resource("s3")
            try:
                if _s3.Bucket(resource_id) in _s3.buckets.all():
                    props = self.cloud_control_attributes_mapping_lookup(
                        cfn_resource_type, resource_id
                    )
            except _s3.meta.client.exceptions:
                LOG.warning(
                    f"{self.module_name}.{self.name} - Failed to evaluate bucket ownership. Cannot use Control API"
                )
        if not props:
            props = self.native_attributes_mapping_lookup(
                get_account_id(self.lookup_session), resource_id, native_lookup_function
            )
        self.mappings = props


class XStack(ComposeXStack):
    """
    Class to handle S3 buckets
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Bucket, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, True)
        if new_resources:
            stack_template = build_template(
                f"S3 root by ECS ComposeX for {settings.name}"
            )
            super().__init__(title, stack_template, **kwargs)
            create_s3_template(new_resources, stack_template)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            self.define_bucket_mappings(lookup_resources, use_resources, settings)
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self

    def define_bucket_mappings(self, lookup_buckets, use_buckets, settings):
        """
        Method to define CFN Mappings for the lookup buckets

        :param list[Bucket] lookup_buckets:
        :param use_buckets:
        :param settings:
        :return:
        """
        for bucket in lookup_buckets:
            bucket.lookup_resource(
                S3_BUCKET_ARN_RE, get_bucket_config, CfnBucket.resource_type, "s3"
            )
            settings.mappings[RES_KEY].update({bucket.logical_name: bucket.mappings})
            if not keyisset(S3_BUCKET_KMS_KEY.return_value, bucket.mappings):
                LOG.info(
                    f"{bucket.module_name}.{bucket.name} - No CMK Key identified. Not KMS permissions to set."
                )
            else:
                LOG.info(
                    f"{bucket.module_name}.{bucket.name} - "
                    f"CMK identified {bucket.mappings[S3_BUCKET_KMS_KEY.return_value]}."
                )
        for bucket in use_buckets:
            if bucket.use.startswith("arn:aws"):
                bucket_arn = bucket.use
                try:
                    bucket_name = S3_BUCKET_ARN_RE.match(bucket_arn).group("id")
                except AttributeError:
                    raise ValueError(
                        "Could not determine the bucket name from the give ARN",
                        bucket.use,
                    )
                LOG.info(
                    f"Determined bucket name is {bucket_name} from arn {bucket_arn}"
                )
            else:
                bucket_name = bucket.use
                bucket_arn = f"arn:aws:s3:::{bucket_name}"
                LOG.warning(
                    "In the absence of a full ARN, assuming partition to be `aws`. Set full ARN to rectify"
                )
                LOG.warning(f"ARN for {bucket_name} is set to {bucket_arn}")
            settings.mappings[RES_KEY].update(
                {
                    bucket.logical_name: {
                        bucket.logical_name: bucket_name,
                        "Arn": bucket_arn,
                    }
                }
            )
