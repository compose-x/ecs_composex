#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from troposphere import GetAtt, Ref

from ecs_composex.common import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.vpc.vpc_params import APP_SUBNETS


def add_iam_dependency(iam_stack: ComposeXStack, family):
    """
    Adds the IAM Stack as dependency to the family one if not set already

    :param ecs_composex.common.stacks.ComposeXStack iam_stack:
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    """
    if iam_stack.title not in family.stack.DependsOn:
        family.stack.DependsOn.append(iam_stack.title)


def update_families_networking_settings(settings, vpc_stack):
    """
    Function to update the families network settings prior to rendering the ECS Service settings

    :param settings: Runtime Execution setting
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :param vpc_stack: The VPC stack and details
    :type vpc_stack: ecs_composex.vpc.vpc_stack.VpcStack
    """
    for family in settings.families.values():
        if family.launch_type == "EXTERNAL":
            LOG.debug(f"{family.name} Ingress cannot be set (EXTERNAL mode). Skipping")
            continue
        if vpc_stack.vpc_resource.mappings:
            family.stack.set_vpc_params_from_vpc_stack_import(vpc_stack)
        else:
            family.stack.set_vpc_parameters_from_vpc_stack(vpc_stack)
        family.add_security_group()
        family.ecs_service.subnets = Ref(APP_SUBNETS)


def update_families_network_ingress(settings):
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


def handle_families_cross_dependencies(settings, root_stack):
    from ecs_composex.ecs.ecs_stack import ServiceStack
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


def set_families_ecs_service(settings):
    """
    Sets the ECS Service in the family.ecs_service from ServiceConfig and family settings
    """
    for family in settings.families.values():
        family.ecs_service.generate_service_definition(settings)
        family.service_scaling.create_scalable_target(family)
        family.service_scaling.add_target_scaling(family)
