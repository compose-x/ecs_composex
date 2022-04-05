# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from ecs_composex.common.cfn_params import Parameter

S3_ARN_REGEX = r"arn:(aws|aws-gov|aws-cn):s3:::([a-zA-Z0-9-.]+$)"

S3_BUCKET_ARN_T = "BucketArn"
S3_BUCKET_ARN = Parameter(
    S3_BUCKET_ARN_T,
    return_value="Arn",
    Type="String",
    AllowedPattern=S3_ARN_REGEX,
)
S3_BUCKET_NAME_T = "BucketName"
S3_BUCKET_NAME = Parameter(
    S3_BUCKET_NAME_T, Type="String", AllowedPattern=r"^[a-z0-9-.]+$"
)
S3_BUCKET_DOMAIN_NAME_T = "BucketDomainName"
S3_BUCKET_DOMAIN_NAME = Parameter(
    S3_BUCKET_DOMAIN_NAME_T, return_value="DomainName", Type="String"
)

S3_BUCKET_REGION_DOMAIN_NAME_T = "BucketDomainName"
S3_BUCKET_REGION_DOMAIN_NAME = Parameter(
    S3_BUCKET_REGION_DOMAIN_NAME_T,
    return_value="RegionalDomainName",
    Type="String",
)

S3_BUCKET_KMS_KEY_T = "BucketKmsKey"
S3_BUCKET_KMS_KEY = Parameter(
    S3_BUCKET_KMS_KEY_T,
    return_value="KMSMasterKeyID",
    Type="String",
    Description="S3 Bucket KMS Key",
)

CONTROL_CLOUD_ATTR_MAPPING = {
    S3_BUCKET_NAME: "BucketName",
    S3_BUCKET_REGION_DOMAIN_NAME: "RegionalDomainName",
    S3_BUCKET_DOMAIN_NAME: "DomainName",
    S3_BUCKET_KMS_KEY: "BucketEncryption::ServerSideEncryptionConfiguration::"
    "0::ServerSideEncryptionByDefault::KMSMasterKeyID",
    S3_BUCKET_ARN: "Arn",
}
