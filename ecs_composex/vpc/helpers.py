#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from ecs_composex.common import LOG, add_update_mapping
from ecs_composex.compose.x_resources.network_x_resources import NetworkXResource


def update_network_resources_vpc_config(settings, vpc_stack):
    """
    Iterate over the settings.x_resources, over the root stack nested stacks.
    If the nested stack has x_resources that depend on VPC, update the stack parameters with the vpc stack settings

    Although the first if should never be true, setting condition in case for safety.

    :param settings: Runtime Execution setting
    :type settings: ecs_composex.common.settings.ComposeXSettingsngs
    :param vpc_stack: The VPC stack and details
    :type vpc_stack: ecs_composex.vpc.vpc_stack.VpcStack
    """
    for resource in settings.x_resources:
        if resource.mappings:
            LOG.debug(
                f"{resource.module.res_key}.{resource.name} - Lookup resource need no VPC Settings."
            )
            continue
        if not resource.requires_vpc:
            LOG.debug(
                f"{resource.module.res_key}.{resource.name} - Resource is not bound to VPC."
            )
            continue
        if not issubclass(type(resource), NetworkXResource):
            LOG.debug(
                f"{resource.module.res_key}.{resource.name} - Not a NetworkXResource"
            )
        if (
            hasattr(resource.stack, "stack_parent")
            and resource.stack.parent_stack is None
        ) or resource.stack == resource.stack.get_top_root_stack():
            LOG.debug(f"{resource.stack.title} is not a nested stacks")
            if vpc_stack.vpc_resource.mappings:
                resource.stack.set_vpc_params_from_vpc_stack_import(vpc_stack)
            else:
                resource.stack.set_vpc_parameters_from_vpc_stack(vpc_stack)
        if resource.requires_vpc and hasattr(resource, "update_from_vpc"):
            resource.update_from_vpc(vpc_stack, settings)


def define_vpc_settings(settings, vpc_module, vpc_stack, root_stack):
    """
    Function to deal with vpc stack settings

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack: The VPC stack and details
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    """
    if settings.requires_vpc() and not vpc_stack.vpc_resource:
        LOG.info(
            f"{settings.name} - Services or x-Resources need a VPC to function. Creating default one"
        )
        vpc_stack.create_new_default_vpc("vpc", vpc_module, settings)
        root_stack.stack_template.add_resource(vpc_stack)
        vpc_stack.vpc_resource.generate_outputs()
    elif (
        vpc_stack.is_void and vpc_stack.vpc_resource and vpc_stack.vpc_resource.mappings
    ):
        vpc_stack.vpc_resource.generate_outputs()
        add_update_mapping(
            root_stack.stack_template, "Network", vpc_stack.vpc_resource.mappings
        )
    elif (
        vpc_stack.vpc_resource
        and vpc_stack.vpc_resource.cfn_resource
        and vpc_stack.title not in root_stack.stack_template.resources.keys()
    ):
        root_stack.stack_template.add_resource(vpc_stack)
        LOG.info(f"{settings.name}.x-vpc - VPC stack added. A new VPC will be created.")
        vpc_stack.vpc_resource.generate_outputs()
