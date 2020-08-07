#  -*- coding: utf-8 -*-
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

from botocore.exceptions import ClientError

from troposphere import If, Ref
from troposphere import AWS_STACK_NAME
from troposphere.ecs import Cluster, CapacityProviderStrategyItem

from ecs_composex.common import LOG, keyisset
from ecs_composex.ecs.ecs_conditions import (
    GENERATED_CLUSTER_NAME_CON_T,
    GENERATED_CLUSTER_NAME_CON,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T, CLUSTER_T
from ecs_composex.ecs import metadata


RES_KEY = "x-cluster"
FARGATE_PROVIDER = "FARGATE"
FARGATE_SPOT_PROVIDER = "FARGATE_SPOT"
DEFAULT_PROVIDERS = [FARGATE_PROVIDER, FARGATE_SPOT_PROVIDER]
DEFAULT_STRATEGY = [
    CapacityProviderStrategyItem(
        Weight=2, Base=1, CapacityProvider=FARGATE_SPOT_PROVIDER
    ),
    CapacityProviderStrategyItem(Weight=1, CapacityProvider=FARGATE_PROVIDER),
]


def get_default_cluster_config():
    """
    Function to get the default defined ECS Cluster configuration

    :return: cluster
    :rtype: troposphere.ecs.Cluster
    """

    return Cluster(
        CLUSTER_T,
        ClusterName=If(
            GENERATED_CLUSTER_NAME_CON_T, Ref(AWS_STACK_NAME), Ref(CLUSTER_NAME_T)
        ),
        CapacityProviders=DEFAULT_PROVIDERS,
        DefaultCapacityProviderStrategy=DEFAULT_STRATEGY,
        Metadata=metadata,
    )


def lookup_ecs_cluster(session, cluster_lookup):
    """
    Function to find the ECS Cluster.

    :param boto3.session.Session session: Boto3 session to make API calls.
    :param cluster_lookup: Cluster lookup definition.
    :return:
    """
    if not isinstance(cluster_lookup, str):
        raise TypeError(
            "The value for Lookup must be", str, "Got", type(cluster_lookup)
        )
    client = session.client("ecs")
    try:
        cluster_r = client.describe_clusters(clusters=[cluster_lookup])
        if not keyisset("clusters", cluster_r):
            LOG.warning(
                f"No cluster named {cluster_lookup} found. Creating one with default settings"
            )
            return get_default_cluster_config()
        elif (
            keyisset("clusters", cluster_r)
            and cluster_r["clusters"][0]["clusterName"] == cluster_lookup
        ):
            LOG.info(
                f"Found ECS Cluster {cluster_lookup}. Setting {CLUSTER_NAME_T} accordingly."
            )
            return cluster_r["clusters"][0]["clusterName"]
    except ClientError as error:
        LOG.error(error)
        raise


def import_capacity_strategy(strategy_def):
    """
    Function to create the Capacity Provider strategies.

    :param strategy_def:
    :return:
    """
    strategies = []
    if not isinstance(strategy_def, list):
        raise ValueError("DefaultCapacityProviderStrategy must be a list")
    for strategy in strategy_def:
        strategies.append(CapacityProviderStrategyItem(**strategy))
    return strategies


def define_cluster(root_stack, cluster_def):
    """
    Function to create the cluster from provided properties.

    :param dict cluster_def:
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :return: cluster
    :rtype: troposphere.ecs.Cluster
    """
    cluster_params = {}
    if not keyisset("Properties", cluster_def):
        return get_default_cluster_config()
    props = cluster_def["Properties"]
    if keyisset("ClusterName", props):
        root_stack.Parameters.update({CLUSTER_NAME_T: props["ClusterName"]})
    if not keyisset("CapacityProviders", props):
        LOG.warning("No capacity providers defined. Setting it to default.")
        cluster_params["CapacityProviders"] = DEFAULT_PROVIDERS
    else:
        cluster_params["CapacityProviders"] = props["CapacityProviders"]
    if not keyisset("DefaultCapacityProviderStrategy", props):
        LOG.warning("No Default Strategy set. Setting to default.")
        cluster_params["DefaultCapacityProviderStrategy"] = DEFAULT_STRATEGY
    else:
        cluster_params["DefaultCapacityProviderStrategy"] = import_capacity_strategy(
            props["DefaultCapacityProviderStrategy"]
        )
    cluster_params["Metadata"] = metadata
    cluster_params["ClusterName"] = If(
        GENERATED_CLUSTER_NAME_CON_T, Ref(AWS_STACK_NAME), Ref(CLUSTER_NAME_T)
    )
    cluster = Cluster(CLUSTER_T, **cluster_params)
    return cluster


def generate_cluster(root_stack, settings):
    """
    Function to create the ECS Cluster.

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    cluster = get_default_cluster_config()
    if not keyisset(RES_KEY, settings.compose_content):
        return cluster
    if keyisset(RES_KEY, settings.compose_content) and keyisset(
        "Lookup", settings.compose_content[RES_KEY]
    ):
        cluster = lookup_ecs_cluster(
            settings.session, settings.compose_content[RES_KEY]["Lookup"]
        )
    elif keyisset(RES_KEY, settings.compose_content) and isinstance(
        settings.compose_content[RES_KEY], str
    ):
        cluster = settings.compose_content[RES_KEY]
        LOG.info(f"Using cluster {settings.compose_content[RES_KEY]}")

    elif isinstance(settings.compose_content[RES_KEY], dict) and keyisset(
        "Use", settings.compose_content[RES_KEY]
    ):
        cluster = settings.compose_content[RES_KEY]["Use"]
        LOG.info(f"Using cluster {settings.compose_content[RES_KEY]['Use']}")
    elif keyisset(RES_KEY, settings.compose_content) and not keyisset(
        "Lookup", settings.compose_content[RES_KEY]
    ):
        cluster = define_cluster(root_stack, settings.compose_content[RES_KEY])
    return cluster


def add_ecs_cluster(settings, root_stack):
    """
    Function to add the cluster to the root template.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    """
    root_stack.stack_template.add_condition(
        GENERATED_CLUSTER_NAME_CON_T, GENERATED_CLUSTER_NAME_CON
    )
    cluster = generate_cluster(root_stack, settings)
    if isinstance(cluster, Cluster):
        root_stack.stack_template.add_resource(cluster)
        return True
    elif isinstance(cluster, str):
        root_stack.Parameters.update({CLUSTER_NAME_T: cluster})
        return False
