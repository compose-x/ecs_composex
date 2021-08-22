#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to define the entry point for AWS Event Rules
"""
import warnings

from ecs_composex.common import LOG, NONALPHANUM, build_template
from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, FARGATE_VERSION
from ecs_composex.events.events_params import MOD_KEY, RES_KEY
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
        set_resources(settings, Rule, RES_KEY, MOD_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources or use_resources:
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
        if lookup_resources or use_resources:
            warnings.warn(
                f"{RES_KEY} does not support Lookup. You can only create new resources"
            )
