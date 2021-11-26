#   -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from troposphere import FindInMap

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params, metadata
from ecs_composex.ecs.ecs_service_network_config import set_compose_services_ingress
from ecs_composex.ecs.ecs_template import (
    initialize_family_services,
    initialize_service_template,
)


class ServiceStack(ComposeXStack):
    """
    Class to identify specifically a service stack
    """


def handle_families_dependencies(settings, families_post):
    """
    Function to handle family to family services based on docker compose depends_on

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list families_post:
    """
    for family in families_post:
        for family_name in settings.families[family].services_depends_on:
            if family_name not in families_post:
                continue
            if family_name not in settings.families[family].stack.DependsOn:
                LOG.info(f"Adding dependency between {family_name} and {family}")
                settings.families[family].stack.DependsOn.append(
                    settings.families[family_name].stack.title
                )


def associate_services_to_root_stack(root_stack, settings, vpc_stack=None):
    """
    Function to generate all services and associate their stack to the root stack

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack vpc_stack:
    :return:
    """
    for family_name, family in settings.families.items():
        family.template = initialize_service_template(family.logical_name)
        family.stack = ServiceStack(
            family.logical_name,
            stack_template=family.template,
            stack_parameters=family.stack_parameters,
        )
        initialize_family_services(settings, family)
        add_parameters(
            family.template,
            [
                family.task_role.arn["ImportParameter"],
                family.task_role.name["ImportParameter"],
                family.exec_role.arn["ImportParameter"],
                family.exec_role.name["ImportParameter"],
            ],
        )
        family.stack.Parameters.update(
            {
                ecs_params.CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier,
                ecs_params.FARGATE_VERSION.title: FindInMap(
                    "ComposeXDefaults", "ECS", "PlatformVersion"
                ),
                family.task_role.arn["ImportParameter"].title: family.task_role.arn[
                    "ImportValue"
                ],
                family.task_role.name["ImportParameter"].title: family.task_role.name[
                    "ImportValue"
                ],
                family.exec_role.arn["ImportParameter"].title: family.exec_role.arn[
                    "ImportValue"
                ],
                family.exec_role.name["ImportParameter"].title: family.exec_role.name[
                    "ImportValue"
                ],
                ecs_params.SERVICE_HOSTNAME.title: family.family_hostname,
            }
        )
        if settings.ecs_cluster.platform_override:
            family.launch_type = settings.ecs_cluster.platform_override
            family.stack.Parameters.update(
                {ecs_params.LAUNCH_TYPE.title: settings.ecs_cluster.platform_override}
            )
        if not vpc_stack:
            family.stack.no_vpc_parameters(settings)
        else:
            family.stack.get_from_vpc_stack(vpc_stack)
        family.template.set_metadata(metadata)
        root_stack.stack_template.add_resource(family.stack)
        if settings.networks and family.service_config.network.networks:
            family.update_family_subnets(settings)

    families_post = [
        family
        for family in root_stack.stack_template.resources
        if (
            family in settings.families
            and isinstance(settings.families[family].stack, ServiceStack)
        )
    ]
    handle_families_dependencies(settings, families_post)
    for family in families_post:
        set_compose_services_ingress(
            root_stack, settings.families[family], families_post, settings
        )
