#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re

from botocore.exceptions import ClientError
from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_STACK_NAME, FindInMap, Ref
from troposphere.ecs import CapacityProviderStrategyItem, Cluster

from ecs_composex.common import LOG
from ecs_composex.ecs import metadata
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_T
from ecs_composex.resources_import import import_record_properties

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
        ClusterName=Ref(AWS_STACK_NAME),
        CapacityProviders=DEFAULT_PROVIDERS,
        DefaultCapacityProviderStrategy=DEFAULT_STRATEGY,
        Metadata=metadata,
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
            f"{cluster_def['clusterName']} - "
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
    providers_strategies = []
    if keyisset("capacityProviders", cluster_def):
        providers = cluster_def["capacityProviders"]
    if keyisset("defaultCapacityProviderStrategy", cluster_def):
        providers_strategies = [
            provider["capacityProvider"]
            for provider in cluster_def["defaultCapacityProviderStrategy"]
        ]
    if not providers and not providers_strategies:
        LOG.warning(
            f"{cluster_def['clusterName']} - No capacityProvider nor defaultCapacityProviderStrategy defined."
            "Overriding to EC2"
        )
    elif providers and providers_strategies:
        for name in providers_strategies:
            if name not in providers:
                providers.append(name)
    return providers


def define_cluster_lookup_props(cluster_r, settings):
    cluster_mapping = {}
    if not cluster_r:
        return cluster_mapping

    cluster_mapping = {CLUSTER_NAME.title: {"Name": cluster_r["clusterName"]}}
    settings.ecs_cluster_providers = evaluate_capacity_providers(cluster_r)
    settings.ecs_cluster_platform_override = evaluate_fargate_is_set(
        settings.ecs_cluster_providers, cluster_r
    )
    return cluster_mapping


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
            return None
        elif (
            keyisset("clusters", cluster_r)
            and cluster_r["clusters"][0]["clusterName"] == cluster_lookup
        ):
            LOG.info(
                f"Found ECS Cluster {cluster_lookup}. Setting {CLUSTER_NAME.title} accordingly."
            )
            return cluster_r["clusters"][0]
    except ClientError as error:
        LOG.error(error)
        raise


def define_cluster(cluster_def):
    """
    Function to create the cluster from provided properties.

    :param dict cluster_def:
    :return: cluster
    :rtype: troposphere.ecs.Cluster
    """
    compose_props = cluster_def["Properties"]
    props = import_record_properties(compose_props, Cluster)
    props["Metadata"] = metadata
    if not keyisset("ClusterName", props):
        props["ClusterName"] = Ref(AWS_STACK_NAME)
    if keyisset("DefaultCapacityProviderStrategy", props) and not keyisset(
        "CapacityProviders", props
    ):
        raise KeyError(
            "When specifying DefaultCapacityProviderStrategy"
            " you must specify CapacityProviders"
        )
    cluster = Cluster(CLUSTER_T, **props)
    return cluster


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
    compose_content[RES_KEY] = {"Use": cluster_name}


def new_cluster_settings_config(cluster_identifier, settings):
    """
    When creating a new cluster, define additional ComposeXSettings values.

    :param troposphere.ecs.Cluster cluster_identifier:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    settings.ecs_cluster = Ref(cluster_identifier)
    settings.ecs_cluster_providers = (
        cluster_identifier.CapacityProviders
        if hasattr(cluster_identifier, "CapacityProviders")
        else []
    )


def add_ecs_cluster(root_stack, settings):
    """
    Function to create the ECS Cluster.

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    cluster_identifier = Ref(AWS_STACK_NAME)
    cluster_mapping = {}
    if keyisset("x-aws-cluster", settings.compose_content):
        import_from_x_aws_cluster(settings.compose_content)
        LOG.info("x-aws-cluster was set. Overriding any defined x-cluster settings")
    if not keyisset(RES_KEY, settings.compose_content):
        LOG.info("No cluster information provided. Creating a new one")
        cluster_identifier = root_stack.stack_template.add_resource(
            get_default_cluster_config()
        )
    elif isinstance(settings.compose_content[RES_KEY], dict):
        if keyisset("Use", settings.compose_content[RES_KEY]):
            LOG.info(f"Using cluster {settings.compose_content[RES_KEY]['Use']}")
            cluster_mapping = {
                CLUSTER_NAME.title: {"Name": settings.compose_content[RES_KEY]["Use"]}
            }
        elif keyisset("Lookup", settings.compose_content[RES_KEY]):
            cluster_r = lookup_ecs_cluster(
                settings.session,
                settings.compose_content[RES_KEY]["Lookup"],
            )
            cluster_mapping = define_cluster_lookup_props(cluster_r, settings)
        elif keyisset("Properties", settings.compose_content[RES_KEY]):
            cluster_identifier = define_cluster(settings.compose_content[RES_KEY])
            root_stack.stack_template.add_resource(cluster_identifier)
    if cluster_mapping:
        root_stack.stack_template.add_mapping("Ecs", cluster_mapping)
        cluster_identifier = FindInMap("Ecs", CLUSTER_NAME.title, "Name")

    if isinstance(cluster_identifier, Cluster):
        new_cluster_settings_config(cluster_identifier, settings)
    else:
        settings.ecs_cluster = cluster_identifier
