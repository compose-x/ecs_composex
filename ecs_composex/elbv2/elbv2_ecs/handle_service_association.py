#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_NO_VALUE, Ref
from troposphere.ecs import LoadBalancer as EcsLb

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_outputs, add_parameters
from ecs_composex.ecs.ecs_params import ELB_GRACE_PERIOD
from ecs_composex.elbv2.elbv2_ecs.common import (
    handle_sg_lb_ingress_to_service,
    setup_template,
)
from ecs_composex.elbv2.elbv2_ecs.target_helpers import (
    import_target_group_attributes,
    set_healthcheck_definition,
    validate_props_and_service_definition,
)
from ecs_composex.elbv2.elbv2_params import TGT_GROUP_ARN
from ecs_composex.elbv2.resources.compose_target_group import ComposeTargetGroup
from ecs_composex.vpc.vpc_params import VPC_ID


def define_service_target_group(
    resource: Elbv2,
    family: ComposeFamily,
    service: ComposeService,
    resources_root_stack: ComposeXStack,
    target_definition: dict,
) -> ComposeTargetGroup:
    """
    Function to create the elbv2 target group
    """
    props = {}
    set_healthcheck_definition(props, target_definition)
    props["Port"] = target_definition["port"]
    props["Protocol"] = (
        props["HealthCheckProtocol"]
        if not keyisset("protocol", target_definition)
        else target_definition["protocol"]
    )
    props["ProtocolVersion"] = set_else_none(
        "ProtocolVersion", target_definition, Ref(AWS_NO_VALUE)
    )
    props["TargetType"] = "ip"
    import_target_group_attributes(props, target_definition, resource)
    validate_props_and_service_definition(props, service)
    target_group_name = f"Tgt{resource.logical_name}{family.logical_name}{service.logical_name}{props['Port']}"
    target_group = ComposeTargetGroup(
        target_group_name,
        elbv2=resource,
        family=family,
        service=service,
        stack=resource.stack,
        port=int(target_definition["port"]),
        VpcId=Ref(VPC_ID),
        **props,
    )
    if target_group.title not in resources_root_stack.stack_template.resources:
        resources_root_stack.stack_template.add_resource(target_group)
    else:
        target_group = resources_root_stack.stack_template.resources[target_group.title]
    target_group.init_outputs()
    target_group.generate_outputs()
    add_outputs(resources_root_stack.stack_template, target_group.outputs)
    if target_group not in family.target_groups:
        family.target_groups.append(target_group)
    tgt_parameter = target_group.attributes_outputs[TGT_GROUP_ARN]["ImportParameter"]
    add_parameters(family.template, [tgt_parameter])
    family.stack.Parameters.update(
        {
            tgt_parameter.title: target_group.attributes_outputs[TGT_GROUP_ARN][
                "ImportValue"
            ],
        }
    )
    service_lb = EcsLb(
        ContainerPort=props["Port"],
        ContainerName=service.name,
        TargetGroupArn=Ref(tgt_parameter),
    )
    family.ecs_service.lbs.append(service_lb)
    add_parameters(family.template, [ELB_GRACE_PERIOD])
    family.ecs_service.ecs_service.HealthCheckGracePeriodSeconds = Ref(ELB_GRACE_PERIOD)
    handle_sg_lb_ingress_to_service(resource, family, resources_root_stack)
    return target_group


def define_service_target_group_definition(
    resource: Elbv2,
    family: ComposeFamily,
    service: ComposeService,
    target_def: dict,
    resources_root_stack: ComposeXStack,
) -> ComposeTargetGroup:
    """
    Function to create the new service TGT Group for a given combination of family, service and port.
    """
    if resource.logical_name not in family.stack.DependsOn:
        family.stack.DependsOn.append(resources_root_stack.title)
        LOG.info(
            f"{resource.module.res_key}.{resource.name} - Adding {family.logical_name} {service.name}"
        )

    return define_service_target_group(
        resource,
        family,
        service,
        resources_root_stack,
        target_def,
    )


def map_service_and_target_group(
    load_balancer: Elbv2,
    family: ComposeFamily,
    target_service: ComposeService,
    service_def: dict,
    res_root_stack: ComposeXStack,
    target_combo_name: str,
    identified: list[bool],
) -> None:
    """
    Maps a service to a target group and associates them with a load balancer.

    Args:
        load_balancer (Elbv2): The load balancer to associate the target group with
        family (ComposeFamily): The ECS service family containing the target service
        target_service (ComposeService): The specific service to create a target group for
        service_def (dict): Service definition containing port and other configuration
        res_root_stack (ComposeXStack): The root stack containing shared resources
        target_combo_name (str): Combined name identifying the target (family:service)
        identified (list[bool]): List to track if target group was successfully mapped

    Creates a target group for the service and maps it to the load balancer's services
    based on matching service names and ports. Updates the service's target ARN reference
    when a match is found.
    """
    tgt_group: ComposeTargetGroup = define_service_target_group_definition(
        load_balancer, family, target_service, service_def, res_root_stack
    )
    for service_name, service in load_balancer.services.items():
        target_name = f"{family.name}:{target_service.name}"
        if target_name not in service_name:
            continue
        if (service_name == target_combo_name) or (
            service_name.find(target_name) == 0
            and tgt_group.Port == int(service["port"])
        ):
            service["target_arn"] = Ref(tgt_group)
            identified.append(True)
            break


def handle_services_association(
    load_balancer: Elbv2, res_root_stack: ComposeXStack, settings: ComposeXSettings
) -> None:
    """
    Associates services and target groups with a load balancer and configures listeners.

    Args:
        load_balancer (Elbv2): The load balancer to associate services with
        res_root_stack (ComposeXStack): The root stack containing shared resources
        settings (ComposeXSettings): Global compose-x settings

    This function:
    1. Sets up the CloudFormation template for the load balancer
    2. Iterates through target families/services to create target groups
    3. Maps services to target groups and configures listeners
    4. Handles listener rules, SSL certs, and Cognito integration

    The function skips services with EXTERNAL launch type and logs an error if no valid
    target services are found to associate with the load balancer.
    """
    # Set up the CloudFormation template with listeners and outputs
    template: Template = setup_template(load_balancer, res_root_stack)
    identified: list[bool] = []

    # Process each target family/service combination
    for target in load_balancer.families_targets:
        family: ComposeFamily = target[0]
        target_service: ComposeService = target[1]
        service_def: dict = target[2]
        target_combo_name: str = target[3]

        # Skip external services
        if target_service.launch_type == "EXTERNAL":
            LOG.error(
                f"x-elbv2.{load_balancer.name} - Target family {family.name} uses EXTERNAL launch type. Ignoring"
            )
            continue

        # Map the service to a target group
        map_service_and_target_group(
            load_balancer,
            family,
            target_service,
            service_def,
            res_root_stack,
            target_combo_name,
            identified,
        )

    # Verify services were mapped successfully
    if not identified:
        LOG.error(
            f"{load_balancer.module.res_key}.{load_balancer.name} - No services found as targets. Skipping association"
        )
        return

    # Configure the load balancer listeners
    handle_services_lb_listeners(load_balancer, res_root_stack, template, settings)


def handle_services_lb_listeners(
    load_balancer: Elbv2,
    res_root_stack: ComposeXStack,
    template: Template,
    settings: ComposeXSettings,
) -> None:
    """
    Configures and sets up load balancer listeners for both new and existing (lookup) listeners.

    Args:
        load_balancer (Elbv2): The load balancer to configure listeners for
        res_root_stack (ComposeXStack): The root stack containing shared resources
        template (Template): The CloudFormation template to add resources to
        settings (ComposeXSettings): Global compose-x settings

    Maps target groups to listeners, handles Cognito user pools, SSL certificates,
    and configures listener rules and default actions.
    """
    # Configure new listeners first
    for listener in load_balancer.new_listeners:
        listener.map_lb_target_groups_service_to_listener_targets(load_balancer)

    # Configure existing (lookup) listeners
    for listener_port, listener in load_balancer.lookup_listeners.items():
        listener.map_lb_target_groups_service_to_listener_targets(load_balancer)
        listener.handle_cognito_pools(settings, res_root_stack)
        listener.define_new_rules(load_balancer, template)

    # Finalize new listener configuration
    for listener in load_balancer.new_listeners:
        listener.handle_certificates(settings, res_root_stack)
        listener.handle_cognito_pools(settings, res_root_stack)
        listener.define_default_actions(load_balancer, template)
