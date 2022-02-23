#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to define the entry point for AWS Event Rules
"""
import warnings

from compose_x_common.compose_x_common import keyisset
from troposphere.events import Rule as CfnRule

from ecs_composex.common import LOG, NONALPHANUM, build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources import (
    ServicesXResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, FARGATE_VERSION
from ecs_composex.events.events_params import MOD_KEY, RES_KEY
from ecs_composex.resources_import import import_record_properties


def define_event_rule(stack, rule):
    """
    Function to define the EventRule properties

    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param ecs_composex.events.events_stack.Rule rule:
    """
    rule_props = import_record_properties(rule.properties, CfnRule)
    if not keyisset("Targets", rule_props):
        rule_props["Targets"] = []
    rule.cfn_resource = CfnRule(rule.logical_name, **rule_props)
    stack.stack_template.add_resource(rule.cfn_resource)


def create_events_template(stack, settings, new_resources):
    """
    Function to create the CFN root template for Events Rules

    :param ecs_composex.events.events_stack.XStack stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list[Rule] new_resources:
    """
    for resource in new_resources:
        if not resource.families_targets:
            LOG.error(
                f"The rule {resource.logical_name} does not have any families_targets defined"
            )
            continue
        define_event_rule(stack, resource)


class Rule(ServicesXResource):
    """
    Class to define an Event Rule
    """

    def handle_families_targets_expansion(self, service, settings):
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        """
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

    def set_services_targets_from_list(self, settings):
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

    def handle_families_targets_expansion_dict(
        self, service_name, service, settings
    ) -> None:
        """
        Method to list all families and services that are targets of the resource.
        Allows to implement family and service level association to resource

        :param str service_name:
        :param dict service: Service definition in compose file
        :param ecs_composex.common.settings.ComposeXSettings settings: Execution settings
        """
        the_service = [s for s in settings.services if s.name == service_name][0]
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

    def set_services_targets_from_dict(self, settings):
        """
        Deals with services set as a dict

        :param settings:
        :return:
        """
        for service_name, service_def in self.services.items():
            if service_name in settings.families and service_name not in [
                f[0].name for f in self.families_targets
            ]:
                self.families_targets.append(
                    (
                        settings.families[service_name],
                        True,
                        settings.families[service_name].services,
                        service_def["TaskCount"],
                        service_def,
                    )
                )
            elif service_name in settings.families and service_name in [
                f[0].name for f in self.families_targets
            ]:
                LOG.debug(
                    f"{self.module_name}.{self.name} - Family {service_name} has already been added. Skipping"
                )
            elif service_name in [s.name for s in settings.services]:
                self.handle_families_targets_expansion_dict(
                    service_name, service_def, settings
                )


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
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        new_resources = set_new_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = build_template(
                "Events rules for ComposeX",
                [CLUSTER_NAME, FARGATE_VERSION],
            )
            super().__init__(title, stack_template, **kwargs)
            create_events_template(self, settings, new_resources)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            warnings.warn(
                f"{RES_KEY} does not support Lookup/Use. You can only create new resources"
            )
