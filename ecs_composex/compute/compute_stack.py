#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

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
