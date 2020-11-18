# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Core module for ECS ComposeX.

This module is going to parse each ecs_service and each x-resource key from the compose file
(hence ComposeX) and determine its

* ServiceDefinition
* TaskDefinition
* TaskRole
* ExecutionRole

It is going to also, based on the labels set in the compose file

* Add the ecs_service to Service Discovery via AWS CloudMap
* Add load-balancers to dispatch traffic to the microservice

"""

from troposphere import Ref, If

from ecs_composex import __version__ as version
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_conditions import CREATE_CLUSTER_CON_T
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_T
from ecs_composex.ecs.ecs_template import generate_services

metadata = {
    "Type": "ComposeX",
    "Properties": {"ecs_composex::module": "ecs_composex.ecs", "Version": version},
}


class ServiceStack(ComposeXStack):
    """
    Class to identify specifically a service stack
    """


def associate_services_to_root_stack(root_stack, settings, dns_params, vpc_stack=None):
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
        family.stack_parameters.update(
            {
                ecs_params.CLUSTER_NAME.title: If(
                    CREATE_CLUSTER_CON_T, Ref(CLUSTER_T), Ref(CLUSTER_NAME)
                ),
            }
        )
        family.stack_parameters.update(dns_params)
        if not vpc_stack:
            family.stack.no_vpc_parameters()
        else:
            family.stack.get_from_vpc_stack(vpc_stack)
        family.template.set_metadata(metadata)
        root_stack.stack_template.add_resource(family.stack)
