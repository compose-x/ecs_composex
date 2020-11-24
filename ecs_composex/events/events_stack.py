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
Module to define the entry point for AWS Event Rules
"""

from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.events.events_params import RES_KEY
from ecs_composex.events.events_template import create_events_template


class Rule(XResource):
    """
    Class to define an Event Rule
    """

    def __init__(self, name, definition, settings):
        super().__init__(name, definition, settings)


class XStack(ComposeXStack):
    """
    Class to handle events stack
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Rule, RES_KEY)
        new_resources = [
            settings.compose_content[RES_KEY][res_name]
            for res_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][res_name].lookup
        ]
        if new_resources:
            stack_template = create_events_template(settings, new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
