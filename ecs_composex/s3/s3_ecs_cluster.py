#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Functions to allow the S3 Bucket to interpolate x-s3 values for ECS Cluster
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.s3.s3_bucket import Bucket
    from ecs_composex.ecs_cluster import EcsCluster
    from troposphere.ecs import ExecuteCommandLogConfiguration
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import GetAtt

from ecs_composex.s3.s3_params import S3_BUCKET_NAME


def interpolate_s3_bucket_name(
    log_config: ExecuteCommandLogConfiguration, bucket: Bucket
) -> None:
    """
    Replaces the value for x-s3::<bucket_name> for the log configuration with the appropriate parameters

    :param log_config:
    :param bucket:
    """
    bucket_id = bucket.attributes_outputs[S3_BUCKET_NAME]
    if bucket.cfn_resource:
        setattr(
            log_config,
            "S3BucketName",
            GetAtt(bucket.stack.title, f"Outputs.{bucket_id['ImportParameter'].title}"),
        )
    elif bucket.mappings:
        setattr(log_config, "S3BucketName", bucket_id["ImportValue"])


def update_cluster_s3_property(ecs_cluster: EcsCluster, bucket: Bucket) -> None:
    """

    :param ecs_cluster:
    :param bucket:
    """
    if not ecs_cluster.cfn_resource or not hasattr(
        ecs_cluster.cfn_resource, "Configuration"
    ):
        return
    configuration = getattr(ecs_cluster.cfn_resource, "Configuration")
    if not hasattr(configuration, "ExecuteCommandConfiguration"):
        return
    exec_config = getattr(configuration, "ExecuteCommandConfiguration")
    if not hasattr(exec_config, "LogConfiguration"):
        return
    log_configuration = getattr(exec_config, "LogConfiguration")
    if not hasattr(log_configuration, "S3BucketName"):
        return
    bucket_name = getattr(log_configuration, "S3BucketName")
    if not bucket_name.startswith(f"{bucket.module.res_key}::") or not isinstance(
        bucket_name, str
    ):
        return
    x_s3_bucket_name = bucket_name.split(r"::")[1]
    if not x_s3_bucket_name == bucket.name:
        return
    interpolate_s3_bucket_name(log_configuration, bucket)


def handle_ecs_cluster(settings: ComposeXSettings, bucket: Bucket) -> None:
    """
    Entrypoint function to updating the ECS Cluster properties

    :param settings:
    :param bucket:
    """
    if settings.ecs_cluster and settings.ecs_cluster.cfn_resource:
        update_cluster_s3_property(settings.ecs_cluster, bucket)
