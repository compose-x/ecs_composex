#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import re

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.ecs_cluster.ecs_cluster_params import (
    FARGATE_PROVIDER,
    FARGATE_SPOT_PROVIDER,
    RES_KEY,
)


def evaluate_fargate_is_set(providers, cluster_def):
    """
    Evaluate if FARGATE or FARGATE_SPOT is defined in the cluster

    :param list[str] providers:
    :param dict cluster_def:
    :return: Whether FARGATE or FARGATE_SPOT is available
    :rtype: bool
    """

    fargate_present = FARGATE_PROVIDER in providers
    fargate_spot_present = FARGATE_SPOT_PROVIDER in providers
    if not fargate_present and not fargate_spot_present:
        LOG.warning(
            f"{cluster_def['ClusterName']} - "
            f"No {FARGATE_PROVIDER} nor {FARGATE_SPOT_PROVIDER} listed in Capacity Providers."
            "Overriding to EC2 Launch Type"
        )
        return "EC2"
    return None


def evaluate_capacity_providers(cluster_def):
    """
    When using Looked'Up cluster, if there is no Fargate Capacity Provider, defined on cluster,
    rollback to EC2 mode.

    :param dict cluster_def:
    :return: List of capacity providers set on the ECS Cluster.
    :rtype: list
    """
    providers = []
    if keyisset("CapacityProviders", cluster_def):
        providers = cluster_def["CapacityProviders"]
    if not providers:
        LOG.warning(
            f"{cluster_def['ClusterName']} - No capacityProvider defined. Fallback to ECS Default"
            "Overriding to EC2"
        )
    return providers


def get_default_capacity_strategy(cluster_def):
    strategy_providers = (
        [
            cap["CapacityProvider"]
            for cap in cluster_def["DefaultCapacityProviderStrategy"]
        ]
        if keyisset("DefaultCapacityProviderStrategy", cluster_def)
        else []
    )
    return strategy_providers


def set_ecs_cluster_identifier(root_stack, settings) -> None:
    """
    Final pass at the top stacks parameters to set the ECS cluster parameter

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for name, resource in root_stack.stack_template.resources.items():
        if issubclass(type(resource), ComposeXStack) and CLUSTER_NAME.title in [
            param.title for param in resource.stack_template.parameters.values()
        ]:
            resource.Parameters.update(
                {CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier}
            )


def import_from_x_aws_cluster(compose_content):
    """
    Function to handle and override settings if x-aws-cluster is defined.

    :param compose_content:
    :return:
    """
    x_aws_key = "x-aws-cluster"
    if not keyisset(x_aws_key, compose_content):
        return
    if compose_content[x_aws_key].startswith("arn:aws"):
        cluster_name = re.sub(
            pattern=r"(arn:aws(?:-[a-z]+)?:ecs:[\S]+:[0-9]{12}:cluster/)",
            repl="",
            string=compose_content[x_aws_key],
        )
    else:
        cluster_name = compose_content[x_aws_key]
    compose_content[RES_KEY] = {"Lookup": {"ClusterName": cluster_name}}
