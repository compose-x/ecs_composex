﻿#  -*- coding: utf-8 -*-
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

import re

from troposphere import (
    AWS_PARTITION,
    AWS_STACK_NAME,
)
from troposphere import Parameter
from troposphere import Ref, Sub, GetAtt
from troposphere.iam import Role as IamRole, Policy as IamPolicy
from troposphere.rds import DBClusterRole

from ecs_composex.common import LOG, keyisset
from ecs_composex.iam import service_role_trust_policy

S3_KEY = "x-s3"


def set_from_x_s3(settings, stack, db, db_template, bucket_name):
    """
    Function to link the RDS DB to a Bucket defined in x-s3

    :param settings:
    :param db:
    :param db_template:
    :param str bucket_name:
    :return:
    """
    resource = None
    if not keyisset(S3_KEY, settings.compose_content):
        raise KeyError(
            f"No Buckets defined in the Compose file under {S3_KEY}.",
            settings.compose_content.keys(),
        )
    bucket_name = bucket_name.strip("x-s3::")
    buckets = settings.compose_content[S3_KEY]
    if bucket_name not in [res.name for res in buckets.values()]:
        LOG.error(
            f"No bucket {bucket_name} in x-s3. Buckets defined: {[res.name for res in buckets.values()]}"
        )
        return
    for resource in buckets.values():
        if bucket_name == resource.name:
            break
    if not resource:
        return
    if resource.cfn_resource:
        param = Parameter(f"{resource.logical_name}Arn", Type="String")
        db_template.add_parameter(param)
        if stack.parent_stack:
            stack.parent_stack.stack_template.add_parameter(param)
            stack.parent_stack.Parameters.update(
                {param.title: GetAtt("s3", f"Outputs.{resource.logical_name}Arn")}
            )
        stack.Parameters.update({param.title: Ref(param.title)})
        return Sub(f"${{{param.title}}}/*")


def add_s3_access(settings, stack, db, config, db_template, subconfig):
    """
    Function to define the IAM Policy for S3Import access

    :param settings:
    :param db:
    :param config:
    :param db_template:
    :param subconfig:
    :return:
    """
    bucket_arn_path_re = re.compile(
        r"(arn:aws:s3:::(?:[a-zA-Z0-9-.]+))(/path/to/files)?"
    )
    bucket_name_path_re = re.compile(r"(?:[a-zA-Z0-9-.]+)(/path/to/files)?")
    bucket_arns = []
    for bucket in config:
        bucket_arn = None
        if not isinstance(bucket, str):
            raise TypeError(
                "All buckets defined in IamAccess/Buckets must be of type",
                str,
                "Got",
                type(bucket),
            )
        if bucket.startswith("x-s3"):
            bucket_arn = set_from_x_s3(settings, stack, db, db_template, bucket)
        elif bucket.startswith("arn:aws"):
            if not bucket_arn_path_re.match(bucket):
                raise ValueError(
                    "The Bucket ARN provided is not valid. Expecting format",
                    bucket_arn_path_re.pattern,
                )
            elif bucket_arn_path_re.match(bucket):
                bucket_arn = bucket
            else:
                bucket_arn = f"{bucket}/*"

        elif not bucket.startswith("arn:aws"):
            if not bucket_name_path_re.match(bucket):
                raise ValueError(
                    "Bucket name and path are not valid. Expecting format",
                    bucket_name_path_re.pattern,
                )
            elif (
                bucket_name_path_re.match(bucket)
                and len(bucket_name_path_re.match(bucket).groups()) == 1
            ):
                bucket_arn = Sub(f"arn:${{{AWS_PARTITION}}}:s3:::{bucket}/*")
            elif (
                bucket_name_path_re.match(bucket)
                and len(bucket_name_path_re.match(bucket).groups()) == 2
            ):
                bucket_arn = Sub(f"arn:${{{AWS_PARTITION}}}:s3:::{bucket}")

        if bucket_arn:
            bucket_arns.append(bucket_arn)

    policy = IamPolicy(
        PolicyName=f"S3AccessFor{db.logical_name}",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3ObjectsAccess",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject*", "s3:PutObject*"],
                    "Resource": bucket_arns,
                }
            ],
        },
    )
    return policy


def add_iam_access(settings, stack, db, data, db_template, boundary):
    """
    Function to add IAM role and permissions to the DB to get access to external resources

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param dict data: The configuration for IamAccess
    :param ecs_composex.rds.rds_stack.Rds db db:
    :param troposphere.Template db_template:
    :param boundary:
    :return:
    """
    print("CONFIG", data)
    if db.cfn_resource and hasattr(db.cfn_resource, "AssociatedRoles"):
        LOG.warning(
            "The db properties already had AssociatedRoles defined."
            " Only will add ones without the feature already defined"
        )
        roles = getattr(db.cfn_resource, "AssociatedRoles")
    else:
        roles = []
    allowed_keys = {
        "Buckets": (list, add_s3_access, "s3Import"),
        "CloudWatch": (bool, None, None),
    }
    if not all(key in allowed_keys.keys() for key in data.keys()):
        raise KeyError(
            "The only valid parameters for IamAccess are",
            allowed_keys.keys(),
            "Got",
            data.keys(),
        )
    for name, subconfig in allowed_keys.items():
        print("ITEM", name, subconfig)
        if keyisset(name, data) and not isinstance(data[name], subconfig[0]):
            LOG.error(
                f"{name} is of type {type(data[name])}. Expected {subconfig[0]}. Skipping"
            )
            continue

        elif (
            keyisset(name, data)
            and isinstance(data[name], subconfig[0])
            and subconfig[1]
        ):
            if (
                roles
                and subconfig[2]
                and subconfig[2] in [role["FeatureName"] for role in roles]
            ):
                LOG.warning(
                    f"Feature {data[2]} is already defined in from the properties. Skipping"
                )
                continue
            else:
                policy = subconfig[1](
                    settings, stack, db, data[name], db_template, subconfig
                )
                print("POLICY", policy)
                role = IamRole(
                    f"{db.logical_name}{subconfig[2]}IamRole",
                    AssumeRolePolicyDocument=service_role_trust_policy("rds"),
                    Description=Sub(
                        f"{db.logical_name}{subconfig[2]}IamRole in ${{{AWS_STACK_NAME}}}"
                    ),
                    Policies=[policy],
                    PermissionsBoundary=boundary,
                    MaxSessionDuration=900,
                )
                db_template.add_resource(role)
                roles.append(
                    DBClusterRole(FeatureName=subconfig[2], RoleArn=GetAtt(role, "Arn"))
                )
        setattr(db.cfn_resource, "AssociatedRoles", roles)
