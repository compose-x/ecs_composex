#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily

from troposphere import GetAtt

from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.service_networking.helpers import add_security_group


def add_iam_dependency(iam_stack: ComposeXStack, family: ComposeFamily):
    """
    Adds the IAM Stack as dependency to the family one if not set already

    :param ecs_composex.common.stacks.ComposeXStack iam_stack:
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    """
    if iam_stack and iam_stack.title not in family.stack.DependsOn:
        family.stack.DependsOn.append(iam_stack.title)


def update_families_networking_settings(
    settings: ComposeXSettings, vpc_stack: ComposeXStack
):
    """
    Function to update the families network settings prior to rendering the ECS Service settings

    :param settings: Runtime Execution setting
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :param vpc_stack: The VPC stack and details
    :type vpc_stack: ecs_composex.vpc.vpc_stack.VpcStack
    """
    for family in settings.families.values():
        if family.service_compute.launch_type == "EXTERNAL":
            LOG.debug(f"{family.name} Ingress cannot be set (EXTERNAL mode). Skipping")
            continue
        if vpc_stack.vpc_resource.mappings:
            family.stack.set_vpc_params_from_vpc_lookup(vpc_stack)
        else:
            family.stack.set_vpc_parameters_from_vpc_stack(vpc_stack, settings)
        add_security_group(family)


def update_families_network_ingress(settings: ComposeXSettings):
    """
    Now that the network settings have been figured out, we can deal with ingress rules

    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """

    for family in settings.families.values():
        if not family.service_networking.security_group:
            continue
        family.service_networking.ingress.set_aws_sources_ingress(
            settings,
            family.logical_name,
            GetAtt(family.service_networking.security_group, "GroupId"),
        )
        family.service_networking.ingress.set_ext_sources_ingress(
            family.logical_name,
            GetAtt(family.service_networking.security_group, "GroupId"),
        )
        family.service_networking.ingress.associate_aws_ingress_rules(family.template)
        family.service_networking.ingress.associate_ext_ingress_rules(family.template)
        family.service_networking.add_self_ingress()


def handle_families_cross_dependencies(
    settings: ComposeXSettings, root_stack: ComposeXStack
):
    from ecs_composex.ecs.ecs_family import ServiceStack
    from ecs_composex.ecs.service_networking.ingress_helpers import (
        set_compose_services_ingress,
    )

    families_stacks = [
        family
        for family in root_stack.stack_template.resources
        if (
            family in settings.families
            and isinstance(settings.families[family].stack, ServiceStack)
        )
    ]
    for family in families_stacks:
        set_compose_services_ingress(
            root_stack, settings.families[family], families_stacks, settings
        )


def set_families_ecs_service(settings: ComposeXSettings):
    """
    Sets the ECS Service in the family.ecs_service from ServiceConfig and family settings
    """
    for family in settings.families.values():
        family.ecs_service.generate_service_definition(family)
        family.service_scaling.create_scalable_target()
        family.service_scaling.add_target_scaling()
