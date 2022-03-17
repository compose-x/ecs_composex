#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere import FindInMap, GetAtt, Join, Ref, StackName, Sub, Tags
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import LOG
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.ecs.ecs_params import SERVICE_NAME, SG_T
from ecs_composex.vpc.vpc_params import APP_SUBNETS, VPC_ID


def add_security_group(family) -> None:
    """
    Creates a new EC2 SecurityGroup and assigns to ecs_service.network_settings
    Adds the security group to the family template resources.

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    """
    family.service_networking.security_group = SecurityGroup(
        SG_T,
        GroupDescription=Sub(
            f"SG for ${{{SERVICE_NAME.title}}} - ${{STACK_NAME}}",
            STACK_NAME=define_stack_name(),
        ),
        Tags=Tags(
            {
                "Name": Sub(
                    f"${{{SERVICE_NAME.title}}}-${{STACK_NAME}}",
                    STACK_NAME=define_stack_name(),
                ),
                "StackName": StackName,
                "MicroserviceName": Ref(SERVICE_NAME),
            }
        ),
        VpcId=Ref(VPC_ID),
    )
    if (
        family.template
        and family.service_networking.security_group.title
        not in family.template.resources
    ):
        family.template.add_resource(family.service_networking.security_group)
    if (
        family.service_networking.security_group
        not in family.ecs_service.security_groups
    ):
        family.ecs_service.security_groups.append(
            Ref(family.service_networking.security_group)
        )


def update_family_subnets(family, settings) -> None:
    """
    Method to update the stack parameters

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    network_names = list(family.service_networking.networks.keys())
    for network in settings.networks:
        if network.name in network_names:
            family.stack_parameters.update(
                {
                    APP_SUBNETS.title: Join(
                        ",",
                        FindInMap("Network", network.subnet_name, "Ids"),
                    )
                }
            )
            LOG.info(
                f"{family.name} - {APP_SUBNETS.title} set to {network.subnet_name}"
            )


def set_family_hostname(family):
    svcs_hostnames = any(svc.family_hostname for svc in family.services)
    if not svcs_hostnames or not family.family_hostname:
        LOG.debug(
            f"{family.name} - No ecs.task.family.hostname defined on any of the services. "
            f"Setting to {family.family_hostname}"
        )
        return
    potential_svcs = []
    for svc in family.services:
        if (
            svc.family_hostname
            and hasattr(svc, "container_definition")
            and svc.container_definition.Essential
        ):
            potential_svcs.append(svc)
    uniq = []
    for svc in potential_svcs:
        if svc.family_hostname not in uniq:
            uniq.append(svc.family_hostname)
    family.family_hostname = uniq[0].lower().replace("_", "-")
    if len(uniq) > 1:
        LOG.warning(
            f"{family.name} more than one essential container has ecs.task.family.hostname set. "
            f"Using the first one {uniq[0]}"
        )
