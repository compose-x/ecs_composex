#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from troposphere import Template

from ecs_composex.common.troposphere_tools import build_template
from ecs_composex.ecs import ecs_conditions, ecs_params


def set_template(family) -> Template:
    """
    Function to set the troposphere.Template associated with the ECS Service Family
    """
    template = build_template(
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
    conditions = {
        ecs_conditions.SERVICE_COUNT_ZERO_CON_T: ecs_conditions.SERVICE_COUNT_ZERO_CON,
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T: ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON,
        ecs_conditions.USE_HOSTNAME_CON_T: ecs_conditions.USE_HOSTNAME_CON,
        ecs_conditions.NOT_USE_HOSTNAME_CON_T: ecs_conditions.NOT_USE_HOSTNAME_CON,
        ecs_conditions.NOT_USE_CLUSTER_SG_CON_T: ecs_conditions.NOT_USE_CLUSTER_SG_CON,
        ecs_conditions.USE_CLUSTER_SG_CON_T: ecs_conditions.USE_CLUSTER_SG_CON,
        ecs_conditions.USE_FARGATE_PROVIDERS_CON_T: ecs_conditions.USE_FARGATE_PROVIDERS_CON,
        ecs_conditions.USE_FARGATE_LT_CON_T: ecs_conditions.USE_FARGATE_LT_CON,
        ecs_conditions.USE_FARGATE_CON_T: ecs_conditions.USE_FARGATE_CON,
        ecs_conditions.NOT_FARGATE_CON_T: ecs_conditions.NOT_FARGATE_CON,
        ecs_conditions.USE_EC2_CON_T: ecs_conditions.USE_EC2_CON,
        ecs_conditions.USE_SERVICE_MODE_CON_T: ecs_conditions.USE_SERVICE_MODE_CON,
        ecs_conditions.USE_CLUSTER_MODE_CON_T: ecs_conditions.USE_CLUSTER_MODE_CON,
        ecs_conditions.USE_EXTERNAL_LT_T: ecs_conditions.USE_EXTERNAL_LT,
        ecs_conditions.USE_LAUNCH_TYPE_CON_T: ecs_conditions.USE_LAUNCH_TYPE_CON,
        ecs_conditions.USE_LINUX_OS_T: ecs_conditions.USE_LINUX_OS,
        ecs_conditions.USE_WINDOWS_OS_T: ecs_conditions.USE_WINDOWS_OS,
        ecs_conditions.IPC_FROM_HOST_CON_T: ecs_conditions.IPC_FROM_HOST_CON,
        ecs_conditions.USE_WINDOWS_OR_FARGATE_T: ecs_conditions.USE_WINDOWS_OR_FARGATE,
        ecs_conditions.DISABLE_CAPACITY_PROVIDERS_CON_T: ecs_conditions.DISABLE_CAPACITY_PROVIDERS_CON,
        ecs_conditions.USE_EC2_OR_EXTERNAL_LT_CON_T: ecs_conditions.USE_EC2_OR_EXTERNAL_LT_CON,
        ecs_conditions.USE_BRIDGE_NETWORKING_MODE_CON_T: ecs_conditions.USE_BRIDGE_NETWORKING_MODE_CON,
        ecs_conditions.USE_AWSVPC_NETWORKING_MODE_CON_T: ecs_conditions.USE_AWSVPC_NETWORKING_MODE_CON,
    }
    for title, condition in conditions.items():
        template.add_condition(title, condition)
    return template
