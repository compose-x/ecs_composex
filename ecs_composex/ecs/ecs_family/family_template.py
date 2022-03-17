#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from ecs_composex.common import build_template
from ecs_composex.ecs import ecs_conditions, ecs_params


def set_template(family):
    """
    Function to set the tropopshere.Template associated with the ECS Service Family
    """
    family.template = build_template(
        f"Template for {family.name}",
        [
            ecs_params.CLUSTER_NAME,
            ecs_params.LAUNCH_TYPE,
            ecs_params.SERVICE_COUNT,
            ecs_params.CLUSTER_SG_ID,
            ecs_params.SERVICE_HOSTNAME,
            ecs_params.FARGATE_CPU_RAM_CONFIG,
            ecs_params.SERVICE_NAME,
            ecs_params.ELB_GRACE_PERIOD,
            ecs_params.FARGATE_VERSION,
            ecs_params.LOG_GROUP_RETENTION,
            ecs_params.RUNTIME_CPU_ARCHITECTURE,
            ecs_params.RUNTIME_OS_FAMILY,
            ecs_params.NETWORK_MODE,
            ecs_params.IPC_MODE,
        ],
    )
    family.template.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_CON_T,
        ecs_conditions.SERVICE_COUNT_ZERO_CON,
    )
    family.template.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON,
    )
    family.template.add_condition(
        ecs_conditions.USE_HOSTNAME_CON_T, ecs_conditions.USE_HOSTNAME_CON
    )
    family.template.add_condition(
        ecs_conditions.NOT_USE_HOSTNAME_CON_T,
        ecs_conditions.NOT_USE_HOSTNAME_CON,
    )
    family.template.add_condition(
        ecs_conditions.NOT_USE_CLUSTER_SG_CON_T,
        ecs_conditions.NOT_USE_CLUSTER_SG_CON,
    )
    family.template.add_condition(
        ecs_conditions.USE_CLUSTER_SG_CON_T, ecs_conditions.USE_CLUSTER_SG_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_FARGATE_PROVIDERS_CON_T,
        ecs_conditions.USE_FARGATE_PROVIDERS_CON,
    )
    family.template.add_condition(
        ecs_conditions.USE_FARGATE_LT_CON_T, ecs_conditions.USE_FARGATE_LT_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_FARGATE_CON_T,
        ecs_conditions.USE_FARGATE_CON,
    )
    family.template.add_condition(
        ecs_conditions.NOT_FARGATE_CON_T, ecs_conditions.NOT_FARGATE_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_EC2_CON_T, ecs_conditions.USE_EC2_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_SERVICE_MODE_CON_T, ecs_conditions.USE_SERVICE_MODE_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_CLUSTER_MODE_CON_T, ecs_conditions.USE_CLUSTER_MODE_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_EXTERNAL_LT_T, ecs_conditions.USE_EXTERNAL_LT
    )
    family.template.add_condition(
        ecs_conditions.USE_LAUNCH_TYPE_CON_T, ecs_conditions.USE_LAUNCH_TYPE_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_LINUX_OS_T, ecs_conditions.USE_LINUX_OS
    )
    family.template.add_condition(
        ecs_conditions.USE_WINDOWS_OS_T, ecs_conditions.USE_WINDOWS_OS
    )
    family.template.add_condition(
        ecs_conditions.IPC_FROM_HOST_CON_T, ecs_conditions.IPC_FROM_HOST_CON
    )
    family.template.add_condition(
        ecs_conditions.USE_WINDOWS_OR_FARGATE_T, ecs_conditions.USE_WINDOWS_OR_FARGATE
    )
