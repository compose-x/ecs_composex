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
Module to create the compute resources, if so chosen, the SpotFleet / OnDemand instances to go with it.

The SpotFleet and OnDemand instances are optional, but the LaunchTemplate gets created so that if
for testing one would wish to run a new EC2 instance, you can simply do it from the launch template.
"""

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compute.compute_template import generate_compute_template


def create_compute_stack(settings):
    """
    Function entrypoint for CLI.

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for execution

    :return: cluster template
    :rtype: troposphere.Template
    """
    template = generate_compute_template(settings)
    return template


class ComputeStack(ComposeXStack):
    """
    Class to handle the EC2 compute creation.
    """

    def __init__(self, title, settings, parameters):
        """
        Method to init the ComputeStack
        :param ecs_composex.common.settings.ComposeXSettings settings: The settings for execution
        """

        template = generate_compute_template(settings)
        super().__init__(title, stack_template=template, stack_parameters=parameters)
