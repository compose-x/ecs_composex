#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from ecs_composex.codeguru_profiler.codeguru_profiler_params import (
    PROFILER_ARN,
    PROFILER_NAME,
)
from ecs_composex.common import LOG, add_outputs
from ecs_composex.resource_settings import (
    assign_new_resource_to_service,
    handle_lookup_resource,
)


def codeguru_profiler_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map new and lookup resources to ECS Services

    :param dict resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for resource_name, resource in resources.items():
        LOG.info(f"{resource.module_name}.{resource_name} - Linking to services")
        if not resource.mappings and resource.cfn_resource:
            resource.init_outputs()
            resource.generate_outputs()
            add_outputs(res_root_stack.stack_template, resource.outputs)
            assign_new_resource_to_service(
                resource, res_root_stack, PROFILER_ARN, [PROFILER_NAME]
            )
        elif resource.mappings and not resource.cfn_resource:
            handle_lookup_resource(settings, resource, PROFILER_ARN)
