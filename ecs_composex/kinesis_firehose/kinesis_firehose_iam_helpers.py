#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kinesis_firehose_stack import DeliveryStream

from compose_x_common.compose_x_common import set_else_none
from troposphere import GetAtt

from ecs_composex.common.logging import LOG


def set_replace_s3_backup_config(resource: DeliveryStream, dest_config) -> None:
    if not hasattr(dest_config, "S3BackupMode") or not hasattr(
        "S3Configuration", dest_config
    ):
        return
    backup_mode = getattr(dest_config, "S3BackupMode")
    if backup_mode == "Disabled":
        return
    s3_backup_config = getattr(dest_config, "S3Configuration")
    setattr(
        s3_backup_config,
        "RoleARN",
        GetAtt(resource.iam_manager.service_linked_role, "Arn"),
    )


def set_replace_iam_role(resource: DeliveryStream) -> None:
    """
    Function to either set, or update, or neither, the RoleARN of

    * "S3DestinationConfiguration"
    * "RedshiftDestinationConfiguration"
    * "KinesisStreamSourceConfiguration"
    * "ExtendedS3DestinationConfiguration"
    * "ElasticsearchDestinationConfiguration"
    * "AmazonopensearchserviceDestinationConfiguration"

    :param DeliveryStream resource:
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
        "KinesisStreamSourceConfiguration",
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
            setattr(
                dest_config,
                "RoleARN",
                GetAtt(resource.iam_manager.service_linked_role, "Arn"),
            )
            set_replace_s3_backup_config(resource, dest_config)
