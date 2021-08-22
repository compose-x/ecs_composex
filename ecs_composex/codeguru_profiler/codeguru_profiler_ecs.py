#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>


from ecs_composex.codeguru_profiler.codeguru_profiler_aws import lookup_profile_config
from ecs_composex.codeguru_profiler.codeguru_profiler_params import (
    MAPPINGS_KEY,
    PROFILER_ARN,
    PROFILER_NAME,
)
from ecs_composex.common import add_outputs
from ecs_composex.resource_settings import (
    assign_new_resource_to_service,
    handle_lookup_resource,
)


def define_lookup_profile_mappings(mappings, resources, settings):
    """
    Function to update the mappings of CodeGuru profile identified via Lookup
    :param dict mappings:
    :param list resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for res in resources:
        mapping = lookup_profile_config(res.lookup, settings.session)
        if mapping:
            res.mappings = mapping
            res.mappings.update({res.logical_name: mapping[PROFILER_NAME.title]})
            mappings.update({res.logical_name: mapping})


def codeguru_profiler_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map new and lookup resources to ECS Services

    :param list resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    resource_mappings = {}
    new_resources = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].cfn_resource
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].mappings
    ]
    for res in new_resources:
        res.init_outputs()
        res.generate_outputs()
        add_outputs(res_root_stack.stack_template, res.outputs)
        assign_new_resource_to_service(
            res, res_root_stack, PROFILER_ARN, [PROFILER_NAME]
        )
    for res in lookup_resources:
        handle_lookup_resource(
            resource_mappings, MAPPINGS_KEY, res, PROFILER_ARN, [PROFILER_NAME]
        )
