#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

"""
Module for the XStack SQS
"""

import sys
from ecs_composex.common import validate_input, keyisset, LOG, EXIT_CODES
from ecs_composex.sqs.sqs_params import RES_KEY
from ecs_composex.sqs.sqs_template import generate_sqs_root_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import set_resources, XResource


def create_sqs_template(settings):
    """
    Creates the CFN Troposphere template

    :param settings: The settings for execution
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return: sqs_tpl
    :rtype: troposphere.Template
    """
    if not keyisset(RES_KEY, settings.compose_content):
        LOG.error(
            f"{RES_KEY} is not defined at all in the docker-compose file {settings.input_file}. Aborting"
        )
        sys.exit(EXIT_CODES["MISSING_RESOURCE_DEFINITION"])
    validate_input(settings.compose_content, RES_KEY)
    sqs_tpl = generate_sqs_root_template(settings)
    return sqs_tpl


class Queue(XResource):
    """
    Class to represent a SQS Queue
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Queue, RES_KEY)
        template = create_sqs_template(settings)
        super().__init__(title, stack_template=template, **kwargs)
