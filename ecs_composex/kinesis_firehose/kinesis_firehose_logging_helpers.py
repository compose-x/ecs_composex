#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import troposphere

if TYPE_CHECKING:
    from .kinesis_firehose_stack import DeliveryStream

from compose_x_common.compose_x_common import set_else_none
from troposphere import GetAtt, Ref
from troposphere.firehose import CloudWatchLoggingOptions
from troposphere.iam import PolicyType
from troposphere.logs import LogStream

from ecs_composex.common.logging import LOG


def grant_log_group_access(stream: DeliveryStream) -> PolicyType:
    policy = PolicyType(
        f"{stream.logical_name}ToCloudWatchLogs",
        PolicyName="CWAccess",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "WriteToCloudWatchLogGroup",
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": GetAtt(stream.log_group, "Arn"),
                }
            ],
        },
        Roles=[Ref(stream.iam_manager.service_linked_role)],
    )
    return policy


def set_replace_cw_logs_config(
    resource: DeliveryStream,
    dest_prop: str,
    dest_config,
    template: troposphere.Template,
) -> None:
    if not hasattr(dest_config, "CloudWatchLoggingOptions"):
        log_stream = template.add_resource(
            LogStream(
                f"{resource.logical_name}{dest_prop}LogStream",
                LogGroupName=Ref(resource.log_group),
                LogStreamName=dest_prop,
            )
        )
        setattr(
            dest_config,
            "CloudWatchLoggingOptions",
            CloudWatchLoggingOptions(
                Enabled=True,
                LogGroupName=Ref(resource.log_group),
                LogStreamName=Ref(log_stream),
            ),
        )

    else:
        cw_config = getattr(dest_config, "CloudWatchLoggingOptions")
        if hasattr(cw_config, "Enabled") and cw_config.Enabled is False:
            LOG.warn(
                f"{resource.module.res_key}.{resource.name}.{dest_prop} - CW Logging explicitly disabled"
            )
        else:
            log_stream = template.add_resource(
                LogStream(
                    f"{resource.logical_name}{dest_prop}LogStream",
                    LogGroupName=Ref(resource.log_group),
                    LogStreamName=dest_prop,
                )
            )
            setattr(cw_config, "LogGroupName", Ref(resource.log_group))
            setattr(cw_config, "LogStreamName", Ref(log_stream))


def set_replace_cw_logging(
    resource: DeliveryStream, template: troposphere.Template
) -> None:
    """
    Function to either set, or update, or neither, the RoleARN of

    * "S3DestinationConfiguration"
    * "RedshiftDestinationConfiguration"
    * "KinesisStreamSourceConfiguration"
    * "ExtendedS3DestinationConfiguration"
    * "ElasticsearchDestinationConfiguration"
    * "AmazonopensearchserviceDestinationConfiguration"

    :param DeliveryStream resource:
    :param troposphere.Template template:
    """
    dont_override = set_else_none(
        "DoNotOverrideIamRole", resource.parameters, eval_bool=True
    )
    if dont_override:
        LOG.info(
            f"{resource.module.res_key}.{resource.name}"
            " - Not overriding any RoleARN defined for delivery destinations"
        )
        return
    to_evaluate_role_arn = [
        "AmazonopensearchserviceDestinationConfiguration",
        "S3DestinationConfiguration",
        "ElasticsearchDestinationConfiguration",
        "ExtendedS3DestinationConfiguration",
        "RedshiftDestinationConfiguration",
    ]
    if dont_override and isinstance(dont_override, bool):
        return
    for dest_prop in to_evaluate_role_arn:
        if not hasattr(resource.cfn_resource, dest_prop):
            LOG.debug(f"{resource.module.res_key}.{resource.name} - No {dest_prop} set")
        elif (
            dont_override
            and isinstance(dont_override, list)
            and dest_prop in dont_override
        ):
            LOG.warn(
                f"f{resource.module.res_key}.{resource.name} - {dest_prop} not overriding with new IAM Role"
            )
        else:
            LOG.debug(
                f"f{resource.module.res_key}.{resource.name} - {dest_prop} overriding with new IAM Role"
            )
            dest_config = getattr(resource.cfn_resource, dest_prop)
            set_replace_cw_logs_config(resource, dest_prop, dest_config, template)
