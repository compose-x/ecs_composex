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

import re
from troposphere.cloudwatch import Alarm as CWAlarm

from ecs_composex.common import (
    LOG,
    keyisset,
    keypresent,
    build_template,
    add_parameters,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import set_resources, XResource
from ecs_composex.resources_import import import_record_properties

from ecs_composex.alarms.alarms_params import RES_KEY


def create_alarms(template, settings, new_alarms):
    """
    Main function to create new alarms
    :return:
    """
    for alarm in new_alarms:
        if not alarm.topics:
            continue
        if alarm.properties:
            props = import_record_properties(alarm.properties, CWAlarm)
            alarm.cfn_resource = CWAlarm(alarm.logical_name, **props)
            template.add_resource(alarm.cfn_resource)


class Alarm(XResource):
    """
    Class to represent CW Alarms
    """

    topics_key = "Topics"

    def __init__(self, name, definition, module_name, settings):
        self.topics = []
        super().__init__(name, definition, module_name, settings)
        self.topics = (
            definition[self.topics_key]
            if keyisset(self.topics_key, self.definition)
            else []
        )


class XStack(ComposeXStack):
    """
    Class to represent the Rootstack for alarms
    """

    def __init__(self, name, settings, **kwargs):
        set_resources(settings, Alarm, RES_KEY)
        new_alarms = [
            settings.compose_content[RES_KEY][db_name]
            for db_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][db_name].lookup
        ]
        if new_alarms and any([alarm.topics for alarm in new_alarms]):
            template = build_template("Root stack for Alarms created via Compose-X")
            super().__init__(name, stack_template=template, **kwargs)
            create_alarms(template, settings, new_alarms)
            self.mark_nested_stacks()
        else:
            self.is_void = True
