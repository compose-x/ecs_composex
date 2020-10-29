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
Module to handle elbv2.
"""

from ecs_composex.common import keyisset

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.compose_resources import XResource, set_resources

from ecs_composex.elbv2.elbv2_params import RES_KEY
from ecs_composex.elbv2.elbv2_template import generate_elbv2_template


class elbv2(XResource):
    """
    Class to handle ELBv2 creation and mapping to ECS Services
    """

    def __init__(self, name, definition, settings):
        super().__init__(name, definition, settings)
        self.validate_services()

    def validate_services(self):
        allowed_keys = [
            ("name", str),
            ("access", str),
            ("port", int),
            ("default", bool),
            ("healthcheck", str),
        ]
        for service in self.services:
            if not all(
                key in [attr[0] for attr in allowed_keys] for key in service.keys()
            ):
                raise KeyError(
                    "Only allowed keys allowed are", [key[0] for key in allowed_keys]
                )
            for key in allowed_keys:
                if keyisset(key[0], service) and not isinstance(
                    service[key[0]], key[1]
                ):
                    raise TypeError(
                        f"{key} should be", key[1], "Got", type(service[key[0]])
                    )


class XStack(ComposeXStack):
    """
    Class to present the ELBv2 root stack
    """

    def __init__(self, title, settings, **kwargs):
        """
        Init ELBv2 stack

        :param str title: title for the new root stack
        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param dict kwargs:
        """
        set_resources(settings, elbv2, RES_KEY)
        resources = settings.compose_content[RES_KEY]
        if [res for res in resources if not res.lookup]:
            stack_template = generate_elbv2_template(settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
