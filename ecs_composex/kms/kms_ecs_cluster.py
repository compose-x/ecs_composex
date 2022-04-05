#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Functions to allow the S3 Bucket to interpolate x-s3 values for ECS Cluster
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.kms.kms_stack import KmsKey
    from ecs_composex.ecs_cluster import EcsCluster
    from troposphere.ecs import ExecuteCommandConfiguration
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import GetAtt

from ecs_composex.kms.kms_params import KMS_KEY_ID


def interpolate_s3_kms_key_id(
    exec_config: ExecuteCommandConfiguration, kms_key: KmsKey
) -> None:
    """
    Replaces the value for x-s3::<kms_key_name> for the log configuration with the appropriate parameters

    :param exec_config:
    :param kms_key:
    """
    kms_key_id = kms_key.attributes_outputs[KMS_KEY_ID]
    if kms_key.cfn_resource:
        setattr(
            exec_config,
            "KmsKeyId",
            GetAtt(
                kms_key.stack.title, f"Outputs.{kms_key_id['ImportParameter'].title}"
            ),
        )
    elif kms_key.mappings:
        setattr(exec_config, "KmsKeyId", kms_key_id["ImportValue"])


def update_cluster_kms_property(ecs_cluster: EcsCluster, kms_key: KmsKey) -> None:
    """

    :param ecs_cluster:
    :param kms_key:
    """
    if not ecs_cluster.cfn_resource or not hasattr(
        ecs_cluster.cfn_resource, "Configuration"
    ):
        return
    configuration = getattr(ecs_cluster.cfn_resource, "Configuration")
    if not hasattr(configuration, "ExecuteCommandConfiguration"):
        return
    exec_config = getattr(configuration, "ExecuteCommandConfiguration")
    interpolate_s3_kms_key_id(exec_config, kms_key)


def handle_ecs_cluster(settings: ComposeXSettings, kms_key: KmsKey) -> None:
    """
    Entrypoint function to updating the ECS Cluster properties

    :param settings:
    :param kms_key:
    """
    if settings.ecs_cluster and settings.ecs_cluster.cfn_resource:
        update_cluster_kms_property(settings.ecs_cluster, kms_key)
