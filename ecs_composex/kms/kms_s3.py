#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handle x-kms in S3 buckets
"""

from troposphere import Ref

from ..common.troposphere_tools import add_parameters
from .kms_params import KMS_KEY_ID

KEY = "KMSMasterKeyID"


def assign_kms_key_to_bucket(kms_key, bucket_rule, bucket_stack):
    """
    Assigns the KMS Key pointer to the bucket property

    :param ecs_composex.kms.kms_stack.KmsKey kms_key:
    :param troposphere.s3.ServerSideEncryptionRule bucket_rule:
    :param ecs_composex.s3.s3_stack.XStack bucket_stack:
    :return:
    """
    kms_key_id = kms_key.attributes_outputs[KMS_KEY_ID]
    add_parameters(bucket_stack.stack_template, [kms_key_id["ImportParameter"]])
    setattr(
        bucket_rule.ServerSideEncryptionByDefault,
        "KMSMasterKeyID",
        Ref(kms_key_id["ImportParameter"]),
    )
    bucket_stack.Parameters.update(
        {kms_key_id["ImportParameter"].title: kms_key_id["ImportValue"]}
    )
    setattr(bucket_rule.ServerSideEncryptionByDefault, "SSEAlgorithm", "aws:kms")


def handle_bucket_kms(kms_key, bucket, bucket_stack, settings):
    """
    Goes over the properties of the bucket and if the KMSMasterKeyID points to the kms_key,
    assigns the value accordingly in the template

    :param ecs_composex.kms.kms_stack.KmsKey kms_key:
    :param ecs_composex.s3.s3_bucket.Bucket bucket:
    :param ecs_composex.s3.s3_stack.XStack bucket_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings: unused
    :return:
    """

    if not bucket.cfn_resource:
        LOG.debug(
            f"{bucket.module.res_key}.{bucket.name} - Not a new resource. Skipping"
        )
        return
    if not hasattr(bucket.cfn_resource, "BucketEncryption"):
        return
    bucket_encryption = bucket.cfn_resource.BucketEncryption
    if not hasattr(bucket_encryption, "ServerSideEncryptionConfiguration"):
        return
    sse_config = bucket_encryption.ServerSideEncryptionConfiguration
    for rule in sse_config:
        if (
            hasattr(rule, "ServerSideEncryptionByDefault")
            and hasattr(rule.ServerSideEncryptionByDefault, "KMSMasterKeyID")
            and isinstance(rule.ServerSideEncryptionByDefault.KMSMasterKeyID, str)
        ):
            key_parts = rule.ServerSideEncryptionByDefault.KMSMasterKeyID.split(
                r"x-kms::"
            )
            if not key_parts or not key_parts[-1] == kms_key.name:
                continue
            assign_kms_key_to_bucket(kms_key, rule, bucket_stack)
