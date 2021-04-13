#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from troposphere import FindInMap

from ecs_composex.common import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params, metadata
from ecs_composex.ecs.ecs_service_network_config import set_compose_services_ingress
from ecs_composex.ecs.ecs_template import generate_services


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
    generate_services(settings)
    for family_name in settings.families:
        family = settings.families[family_name]
        family.stack = ServiceStack(
            family.logical_name,
            stack_template=family.template,
            stack_parameters=family.stack_parameters,
        )
        family.stack.Parameters.update(
            {
                ecs_params.CLUSTER_NAME.title: settings.ecs_cluster,
                ecs_params.FARGATE_VERSION.title: FindInMap(
                    "ComposeXDefaults", "ECS", "PlatformVersion"
                ),
            }
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
