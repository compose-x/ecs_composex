#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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

from troposphere import FindInMap

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params, metadata
from ecs_composex.ecs.ecs_service_network_config import set_compose_services_ingress
from ecs_composex.ecs.ecs_template import generate_services


class ServiceStack(ComposeXStack):
    """
    Class to identify specifically a service stack
    """


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
    for family in families_post:
        set_compose_services_ingress(
            root_stack, settings.families[family], families_post, settings
        )
