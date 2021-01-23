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

"""
Module to define the entry point for AWS Event Rules
"""

from troposphere import Ref, If

from ecs_composex.common import build_template, LOG, NONALPHANUM
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_conditions import CREATE_CLUSTER_CON_T
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_T, FARGATE_VERSION
from ecs_composex.events.events_params import RES_KEY
from ecs_composex.events.events_template import create_events_template


def validate_service_definition(service):
    required_keys = ["name", "TaskCount"]
    if not set(required_keys).issubset(service):
        raise KeyError(
            "Services definition must contain at least",
            required_keys,
            "Got",
            service.keys(),
        )


class Rule(XResource):
    """
    Class to define an Event Rule
    """

    def __init__(self, name, definition, settings):
        super().__init__(name, definition, settings)

    def handle_families_targets_expansion(self, service, settings):
        the_service = [s for s in settings.services if s.name == service["name"]][0]
        for family_name in the_service.families:
            family_name = NONALPHANUM.sub("", family_name)
            if family_name not in [f[0].name for f in self.families_targets]:
                self.families_targets.append(
                    (
                        settings.families[family_name],
                        False,
                        [the_service],
                        service["TaskCount"],
                        service,
                    )
                )

    def set_services_targets(self, settings):
        """
        Override method to map services and families targets of the services defined specifically for
        events
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.info(f"No services defined for {self.name}")
            return
        for service in self.services:
            validate_service_definition(service)
            service_name = service["name"]
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service["TaskCount"],
                        service,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.warning(
                    f"The family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion(service, settings)


class XStack(ComposeXStack):
    """
    Class to handle events stack
    """

    def __init__(self, title, settings, **kwargs):
        """
        Method to initialize the XStack for Events

        :param str title: title for the stack
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        :param dict kwargs:
        """
        set_resources(settings, Rule, RES_KEY)
        new_resources = [
            settings.compose_content[RES_KEY][res_name]
            for res_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][res_name].lookup
        ]
        if new_resources:
            params = {
                CLUSTER_NAME.title: settings.ecs_cluster,
            }
            stack_template = build_template(
                "Events rules for ComposeX",
                [CLUSTER_NAME, FARGATE_VERSION],
            )
            super().__init__(title, stack_template, stack_parameters=params, **kwargs)
            create_events_template(self, settings, new_resources)
        else:
            self.is_void = True
