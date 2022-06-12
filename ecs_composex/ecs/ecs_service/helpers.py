#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>
import re

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import If, NoValue, Ref, StackName, Tags
from troposphere.ecs import (
    DeploymentCircuitBreaker,
    DeploymentConfiguration,
    PlacementStrategy,
)

from ecs_composex.ecs.ecs_conditions import USE_EXTERNAL_LT_T, USE_FARGATE_CON_T
from ecs_composex.ecs.ecs_params import SERVICE_NAME


def define_placement_strategies() -> If:
    """
    Function to generate placement strategies. Defaults to spreading across all AZs

    :return: list of placement strategies
    """
    return If(
        USE_FARGATE_CON_T,
        NoValue,
        If(
            USE_EXTERNAL_LT_T,
            NoValue,
            [
                PlacementStrategy(Field="instanceId", Type="spread"),
                PlacementStrategy(
                    Field="attribute:ecs.availability-zone", Type="spread"
                ),
            ],
        ),
    )


def define_family_deploy_percents(values: list, default: int) -> int:
    """
    Simple function to average out sum of values or return default value
    :param values:
    :param default:
    :return: The default or average value
    """
    if not values:
        return default
    maxis_sum = sum(values)
    if not maxis_sum:
        family_deploy_percent = 0
    else:
        family_deploy_percent = maxis_sum / len(values)

    return int(family_deploy_percent)


def set_service_update_config(family) -> dict:
    """
    Method to determine the update_config for the service. When a family has multiple containers, this applies
    to all tasks.
    """
    deployment_config = {}
    min_percents = [
        int(service.definition["x-aws-min_percent"])
        for service in family.services
        if keypresent("x-aws-min_percent", service.definition)
    ]
    max_percents = [
        int(service.definition["x-aws-max_percent"])
        for service in family.services
        if keypresent("x-aws-max_percent", service.definition)
    ]
    family_min_percent = define_family_deploy_percents(min_percents, 100)
    family_max_percent = define_family_deploy_percents(max_percents, 200)

    rollback = True
    actions = [
        service.update_config["failure_action"] != "rollback"
        for service in family.services
        if service.update_config and keyisset("failure_action", service.update_config)
    ]
    if any(actions):
        rollback = False
    deployment_config.update(
        {
            "MinimumHealthyPercent": family_min_percent,
            "MaximumPercent": family_max_percent,
            "RollBack": rollback,
        }
    )
    return deployment_config


def define_deployment_options(family, props: dict) -> None:
    """
    Function to define the DeploymentConfiguration
    Default is to have Rollback and CircuitBreaker on.

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param dict props: the troposphere.ecs.Service properties definition to update with deployment config.
    """
    default = DeploymentConfiguration(
        DeploymentCircuitBreaker=DeploymentCircuitBreaker(Enable=True, Rollback=True),
    )
    deployment_config = set_service_update_config(family)
    if deployment_config:
        deploy_config = DeploymentConfiguration(
            MaximumPercent=int(deployment_config["MaximumPercent"]),
            MinimumHealthyPercent=int(deployment_config["MinimumHealthyPercent"]),
            DeploymentCircuitBreaker=DeploymentCircuitBreaker(
                Enable=True,
                Rollback=keyisset("RollBack", deployment_config),
            ),
        )
        props.update({"DeploymentConfiguration": deploy_config})
    else:
        props.update({"DeploymentConfiguration": default})


def set_service_default_tags_labels(family) -> Tags:
    """
    Sets default service tags and labels
    """
    service_tags = Tags(
        {
            "Name": Ref(SERVICE_NAME),
            "StackName": StackName,
            "compose-x::name": family.name,
            "compose-x::logical_name": family.logical_name,
        }
    )
    for svc in family.services:
        if not svc.deploy_labels:
            continue
        if isinstance(svc.deploy_labels, list):
            continue
        for key, value in svc.deploy_labels.items():
            if not isinstance(value, str) or (
                isinstance(value, str) and re.match(r"^[a-zA-Z:=+_\-@ ]+$", value)
            ):
                service_tags += Tags(**{key: value})
    return service_tags
