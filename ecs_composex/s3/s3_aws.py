#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Functions to find buckets and identify settings about these.
"""

import re

from botocore.exceptions import ClientError

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.aws import define_tagsgroups_filter_tags
from ecs_composex.s3.s3_params import S3_ARN_REGEX


def lookup_s3_bucket(session, bucket_name=None, tags=None):
    """

    :param boto3.session.Session session:
    :param str bucket_name:
    :param list tags:
    :return:
    """
    if bucket_name is not None:
        client = session.client("s3")
        try:
            client.head_bucket(Bucket=bucket_name)
            return bucket_name
        except client.exceptions.NoSuchBucket:
            return None
        except ClientError as error:
            LOG.error(error)
            raise

    elif bucket_name is None and tags:
        if not isinstance(tags, list):
            raise TypeError("Tags must be a list of key/value dict")
        filters = define_tagsgroups_filter_tags(tags)
        print(filters)
        client = session.client("resourcegroupstaggingapi")
        buckets_r = client.get_resources(
            ResourceTypeFilters=("s3",), TagFilters=filters
        )
        if keyisset("ResourceTagMappingList", buckets_r):
            resources = buckets_r["ResourceTagMappingList"]
            if len(resources) != 1:
                raise LookupError(
                    "Found more than one bucket with the current tags",
                    [resource["ResourceARN"] for resource in resources],
                    "Expected to match only 1 bucket.",
                )
            s3_filter = re.compile(S3_ARN_REGEX)
            return [
                {
                    "Name": s3_filter.match(resources[0]["ResourceARN"]).groups()[-1],
                    "Arn": resources[0]["ResourceARN"],
                }
            ]
    return None
