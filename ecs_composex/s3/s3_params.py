#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from os import path

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
MAPPINGS_KEY = NONALPHANUM.sub("", MOD_KEY)

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
