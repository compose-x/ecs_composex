# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dynamodb_stack import Table
    from troposphere import Template

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import Ref, Sub
from troposphere.applicationautoscaling import (
    PredefinedMetricSpecification,
    ScalableTarget,
    ScalingPolicy,
    TargetTrackingScalingPolicyConfiguration,
)

from ecs_composex.common.logging import LOG

from ..common.troposphere_tools import add_resource


def create_autoscaling_target_and_policy(
    table: Table,
    template: Template,
    scalable_property: str,
    scale_definition: dict,
    index: str = None,
) -> tuple:
    """
    Defines the autoscaling target and policy for the a given resource and dimension.

    :param Table table:
    :param Template template:
    :param str scalable_property:
    :param dict scale_definition:
    :param str index:
    :return: The target and the associated policy
    """
    property_mapping: dict = {
        "WriteCapacityUnits": {
            "PredefinedMetricType": "DynamoDBWriteCapacityUtilization"
        },
        "ReadCapacityUnits": {
            "PredefinedMetricType": "DynamoDBReadCapacityUtilization"
        },
    }
    scablable_resource = (
        Sub(f"table/${{{table.cfn_resource.title}}}")
        if not index
        else Sub(f"table/${{{table.cfn_resource.title}}}/index/{index}")
    )
    target_title = (
        f"{table.logical_name}{scalable_property}ScalableTarget"
        if not index
        else f"{table.logical_name}{scalable_property}Index{index}ScalableTarget"
    )
    scaling_target = ScalableTarget(
        target_title,
        MinCapacity=scale_definition["MinCapacity"],
        MaxCapacity=scale_definition["MaxCapacity"],
        ServiceNamespace="dynamodb",
        ScalableDimension=f"dynamodb:table:{scalable_property}"
        if not index
        else f"dynamodb:index:{scalable_property}",
        RoleARN=Sub(
            "arn:aws:iam::${AWS::AccountId}:role/aws-service-role/"
            "dynamodb.application-autoscaling.${AWS::URLSuffix}/"
            "AWSServiceRoleForApplicationAutoScaling_DynamoDBTable"
        ),
        ResourceId=scablable_resource,
    )
    scaling_policy = ScalingPolicy(
        f"{scaling_target.title}ScalingPolicy",
        DependsOn=[scaling_target.title],
        PolicyName=f"{scalable_property}AutoScalingPolicy",
        PolicyType="TargetTrackingScaling",
        ScalingTargetId=Ref(scaling_target),
        TargetTrackingScalingPolicyConfiguration=TargetTrackingScalingPolicyConfiguration(
            TargetValue=scale_definition["TargetValue"],
            ScaleInCooldown=set_else_none(
                "ScaleInCooldown", scale_definition, alt_value=60
            ),
            ScaleOutCooldown=set_else_none(
                "ScaleOutCooldown", scale_definition, alt_value=60
            ),
            PredefinedMetricSpecification=PredefinedMetricSpecification(
                PredefinedMetricType=property_mapping[scalable_property][
                    "PredefinedMetricType"
                ]
            ),
        ),
    )
    target = add_resource(template, scaling_target)
    policy = add_resource(template, scaling_policy)
    return target, policy


def add_autoscaling_for_table_or_index(
    table: Table, template: Template, scaling_definition: dict, index: str = None
) -> None:
    """
    Function to process WriteCapacityUnits and ReadCapacityUnits defined in scaling

    :param Table table:
    :param Template template:
    :param dict scaling_definition:
    :param str index:
    """
    for key in ["WriteCapacityUnits", "ReadCapacityUnits"]:
        if keyisset(key, scaling_definition):
            target, policy = create_autoscaling_target_and_policy(
                table, template, key, scaling_definition[key], index=index
            )
            if not index:
                table.scaling_target = target


def add_autoscaling_for_indexes(
    table: Table, template: Template, table_indexes: list, indexes_scaling: dict
) -> None:
    """
    Function to process all the scaling defined on indexes

    :param Table table:
    :param Template template:
    :param list table_indexes:
    :param dict indexes_scaling:
    """
    table_gsis = [_table.IndexName for _table in table_indexes]
    processed_indexes = []
    if indexes_scaling:
        for _index_to_scale, scaling_config in indexes_scaling.items():
            for table_index in table_indexes:
                if _index_to_scale == table_index.IndexName:
                    break
            else:
                raise KeyError(
                    f"{table.module.res_key}.{table.name}",
                    f"Scaling for index {_index_to_scale} defined, but index not defined in Properties",
                    table_gsis,
                )
            add_autoscaling_for_table_or_index(
                table, template, scaling_config, index=_index_to_scale
            )
            processed_indexes.append(_index_to_scale)
    cover_indexes_without_scaling_definition(
        table, template, table_gsis, processed_indexes
    )


def cover_indexes_without_scaling_definition(
    table: Table, template: Template, table_gsis: list, processed_indexes: list
) -> None:
    for index in table_gsis:
        if index in processed_indexes:
            continue
        if not keyisset("CopyToIndexes", table.scaling):
            LOG.warning(
                f"{table.module.res_key}.{table.name}"
                f" - no scaling defined for index {index}"
            )
        else:
            LOG.info(
                f"{table.module.res_key}.{table.name}"
                f" - applying same scaling for index {index} as for Table"
            )
            add_autoscaling_for_table_or_index(
                table, template, table.scaling["Table"], index=index
            )


def handle_indexes(table: Table, template: Template) -> None:
    indexes_scaling = set_else_none("Indexes", table.scaling)
    table_indexes = (
        getattr(table.cfn_resource, "GlobalSecondaryIndexes")
        if hasattr(table.cfn_resource, "GlobalSecondaryIndexes")
        else None
    )
    if indexes_scaling and table_indexes:
        add_autoscaling_for_indexes(table, template, table_indexes, indexes_scaling)
    elif table_indexes and not indexes_scaling:
        if not keyisset("CopyToIndexes", table.scaling):
            LOG.warning(
                f"{table.module.res_key}.{table.name} - Scaling defined for Table only, and not for indexes!"
            )
        else:
            add_autoscaling_for_indexes(table, template, table_indexes, indexes_scaling)
    else:
        LOG.warning(
            f"{table.module.res_key}.{table.name}"
            " - Scaling defined for Indexes, but no index defined in table. Skipping!"
        )


def add_autoscaling(table: Table, template: Template) -> None:
    """
    Function to add all the autoscaling resources to a given dynamoDB table

    :param Table table:
    :param Template template:
    """
    table_scaling = table.scaling["Table"]
    add_autoscaling_for_table_or_index(table, template, table_scaling)
    if not hasattr(table.cfn_resource, "BillingMode"):
        setattr(table.cfn_resource, "BillingMode", "PROVISIONED")
    elif table.cfn_resource.BillingMode == "PAY_PER_REQUEST":
        LOG.warning(
            f"{table.module.res_key}.{table.name} - "
            "With Scaling enabled, overriding BillingMode to PROVISIONED"
        )
        setattr(table.cfn_resource, "BillingMode", "PROVISIONED")

    handle_indexes(table, template)
