# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from troposphere import Template
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService

import re

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_NO_VALUE, GetAtt, Output, Ref, Sub
from troposphere.ecs import LoadBalancer as EcsLb
from troposphere.elasticloadbalancingv2 import (
    Matcher,
    TargetGroup,
    TargetGroupAttribute,
)

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_outputs,
    add_parameters,
    add_resource,
)
from ecs_composex.ecs.ecs_params import ELB_GRACE_PERIOD
from ecs_composex.elbv2.elbv2_params import (
    LB_SG_ID,
    TGT_FULL_NAME,
    TGT_GROUP_ARN,
    TGT_GROUP_NAME,
)
from ecs_composex.vpc.vpc_params import VPC_ID


class MergedTargetGroup(TargetGroup):
    """Class for TargetGroup merged among more than one service"""

    def __init__(
        self,
        name: str,
        definition: dict,
        elbv2: Elbv2,
        stack: ComposeXStack,
        port: int,
        **kwargs,
    ):
        self.name = name
        self._definition = definition
        self.families: list[ComposeFamily] = []
        self.stack: ComposeXStack = stack
        self.outputs = []
        self.elbv2: Elbv2 = elbv2
        self.output_properties = {}
        self.attributes_outputs = {}
        super().__init__(NONALPHANUM.sub("", name), **kwargs)

    @property
    def definition(self) -> dict:
        return self._definition

    def init_outputs(self):
        self.output_properties = {
            TGT_GROUP_ARN: (self.title, self, Ref, None),
            TGT_GROUP_NAME: (
                f"{self.title}{TGT_GROUP_NAME.return_value}",
                self,
                GetAtt,
                TGT_GROUP_NAME.return_value,
                None,
            ),
            TGT_FULL_NAME: (
                f"{self.title}{TGT_FULL_NAME.return_value}",
                self,
                GetAtt,
                TGT_FULL_NAME.return_value,
                None,
            ),
        }

    def generate_outputs(self):
        for (
            attribute_parameter,
            output_definition,
        ) in self.output_properties.items():
            output_name = f"{self.title}{attribute_parameter.title}"
            value = self.set_new_resource_outputs(output_definition)
            self.attributes_outputs[attribute_parameter] = {
                "Name": output_name,
                "Output": Output(output_name, Value=value),
                "ImportParameter": Parameter(
                    output_name,
                    return_value=attribute_parameter.return_value,
                    Type=attribute_parameter.Type,
                ),
                "ImportValue": GetAtt(
                    self.stack,
                    f"Outputs.{output_name}",
                ),
                "Original": attribute_parameter,
            }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])

    def set_new_resource_outputs(self, output_definition):
        """
        Method to define the outputs for the resource when new
        """
        if output_definition[2] is Ref:
            value = Ref(output_definition[1])
        elif output_definition[2] is GetAtt:
            value = GetAtt(output_definition[1], output_definition[3])
        elif output_definition[2] is Sub:
            value = Sub(output_definition[3])
        else:
            raise TypeError(
                f"3rd argument for {output_definition[0]} must be one of",
                (Ref, GetAtt, Sub),
                "Got",
                output_definition[2],
            )
        return value

    def associate_families(self, settings: ComposeXSettings):
        for _family in self.definition["Services"]:
            _family_name, _service_name = _family["Name"].split(r":")
            for family in settings.families.values():
                if family.name == _family_name:
                    break
            else:
                raise KeyError(
                    f"{self.elbv2.module.res_key}.{self.elbv2.name} - TargetGroup {self.name} - Service Family {_family_name} is not set in services"
                )
            for _f_service in family.services:
                if _f_service.name == _service_name:
                    break
            else:
                raise KeyError(
                    f"{self.elbv2.module.res_key}.{self.elbv2.name} - TargetGroup {self.name} - Family {_family_name} does not have a container named {_service_name}"
                )

            if self not in family.target_groups:
                family.target_groups.append(self)
            tgt_parameter = self.attributes_outputs[TGT_GROUP_ARN]["ImportParameter"]
            add_parameters(family.template, [tgt_parameter])
            family.stack.Parameters.update(
                {
                    tgt_parameter.title: self.attributes_outputs[TGT_GROUP_ARN][
                        "ImportValue"
                    ],
                }
            )
            service_lb = EcsLb(
                ContainerPort=self.Port,
                ContainerName=_f_service.name,
                TargetGroupArn=Ref(tgt_parameter),
            )
            family.ecs_service.lbs.append(service_lb)
            add_parameters(family.template, [ELB_GRACE_PERIOD])
            family.ecs_service.ecs_service.HealthCheckGracePeriodSeconds = Ref(
                ELB_GRACE_PERIOD
            )
            handle_sg_lb_ingress_to_service(self.elbv2, family, self.elbv2.stack)


class ComposeTargetGroup(TargetGroup):
    """
    Class to manage Target Groups
    """

    def __init__(
        self,
        title: str,
        elbv2: Elbv2,
        family: ComposeFamily,
        service: ComposeService,
        stack: ComposeXStack,
        port: int,
        **kwargs,
    ):
        self.family: ComposeFamily = family
        self.service: ComposeService = service
        self.stack: ComposeXStack = stack
        self.port: int = port
        self.outputs = []
        self.elbv2: Elbv2 = elbv2
        self.output_properties = {}
        self.attributes_outputs = {}
        super().__init__(title, **kwargs)

    def init_outputs(self):
        self.output_properties = {
            TGT_GROUP_ARN: (self.title, self, Ref, None),
            TGT_GROUP_NAME: (
                f"{self.title}{TGT_GROUP_NAME.return_value}",
                self,
                GetAtt,
                TGT_GROUP_NAME.return_value,
                None,
            ),
            TGT_FULL_NAME: (
                f"{self.title}{TGT_FULL_NAME.return_value}",
                self,
                GetAtt,
                TGT_FULL_NAME.return_value,
                None,
            ),
        }

    def generate_outputs(self):
        for (
            attribute_parameter,
            output_definition,
        ) in self.output_properties.items():
            output_name = f"{self.title}{attribute_parameter.title}"
            value = self.set_new_resource_outputs(output_definition)
            self.attributes_outputs[attribute_parameter] = {
                "Name": output_name,
                "Output": Output(output_name, Value=value),
                "ImportParameter": Parameter(
                    output_name,
                    return_value=attribute_parameter.return_value,
                    Type=attribute_parameter.Type,
                ),
                "ImportValue": GetAtt(
                    self.stack,
                    f"Outputs.{output_name}",
                ),
                "Original": attribute_parameter,
            }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])

    def set_new_resource_outputs(self, output_definition):
        """
        Method to define the outputs for the resource when new
        """
        if output_definition[2] is Ref:
            value = Ref(output_definition[1])
        elif output_definition[2] is GetAtt:
            value = GetAtt(output_definition[1], output_definition[3])
        elif output_definition[2] is Sub:
            value = Sub(output_definition[3])
        else:
            raise TypeError(
                f"3rd argument for {output_definition[0]} must be one of",
                (Ref, GetAtt, Sub),
                "Got",
                output_definition[2],
            )
        return value


def handle_ping_settings(props, ping_raw):
    """
    Function to setup the "ping" settings

    :param dict props:
    :param str ping_raw:
    :return:
    """
    ping_re = re.compile(r"^([\d]|10):([\d]|10):([\d]{1,3}):([\d]{1,3})$")
    groups = ping_re.match(ping_raw).groups()
    ping_mapping = (
        ("HealthyThresholdCount", (2, 10)),
        ("UnhealthyThresholdCount", (2, 10)),
        ("HealthCheckIntervalSeconds", (5, 300)),
        ("HealthCheckTimeoutSeconds", (2, 120)),
    )
    for count, value in enumerate(groups):
        if not min(ping_mapping[count][1]) <= int(value) <= max(ping_mapping[count][1]):
            LOG.error(
                f"Value for {ping_mapping[count][0]} is not valid. Must be in range of {ping_mapping[count][1]}"
            )
        props[ping_mapping[count][0]] = int(value)


def handle_path_settings(props: dict, path_raw: str) -> None:
    """
    Function to set the path and codes properties

    :param dict props:
    :param str path_raw:
    :return:
    """
    health_re = re.compile(
        r"(?P<shorty>^/:(?P<codes0>(?:[12345][0-9]{2},?){1,})$)"
        r"|(?P<long>(?P<path1>/[^:]+):(?P<codes1>(?:[12345][0-9]{2},?){1,})$)|"
        r"(?P<codesonly>(?:[12345][0-9]{2},?){1,})$"
    )
    shorty = health_re.search(path_raw).group("shorty")
    long = health_re.search(path_raw).group("long")
    codes_only = health_re.search(path_raw).group("codesonly")

    if shorty:
        props["Matcher"] = Matcher(HttpCode=health_re.search(path_raw).group("codes0"))
    elif long:
        props["HealthCheckPath"] = health_re.search(path_raw).group("path1")
        props["Matcher"] = Matcher(HttpCode=health_re.search(path_raw).group("codes1"))
    elif codes_only:
        props["Matcher"] = Matcher(
            HttpCode=health_re.search(path_raw).group("codesonly")
        )

    if props["HealthCheckProtocol"] not in ["HTTP", "HTTPS"] and isinstance(
        props["Matcher"], Matcher
    ):
        raise ValueError(
            groups,
            "Protocol and return codes are only valid for HTTP and HTTPS HealthCheck",
        )


def set_healthcheck_definition(
    props, target_definition, healtheck_keyword: str = "healthcheck"
):
    """

    :param dict props:
    :param dict target_definition:
    :return:
    """
    healthcheck_props = {
        "HealthCheckEnabled": Ref(AWS_NO_VALUE),
        "HealthCheckIntervalSeconds": Ref(AWS_NO_VALUE),
        "HealthCheckPath": Ref(AWS_NO_VALUE),
        "HealthCheckPort": Ref(AWS_NO_VALUE),
        "HealthCheckProtocol": Ref(AWS_NO_VALUE),
        "HealthCheckTimeoutSeconds": Ref(AWS_NO_VALUE),
        "HealthyThresholdCount": Ref(AWS_NO_VALUE),
    }
    healthcheck_reg = re.compile(
        r"(?:^(?P<port>[\d]{2,5}):(?P<protocol>HTTPS|HTTP|TCP_UDP|TCP|TLS|UDP|GENEVE)):?"
        r"(?P<ping>(?:[\d]{1}|10):(?:[\d]{1}|10):[\d]{1,3}:[\d]{1,3})?:?"
        r"(?P<health>(?:/[\S][^:]+.$)|(?:/[\S][^:]+)(?::)(?:(?:[\d]{1,4},?){1,}.$)|(?:(?:[\d]{1,4},?){1,}.$))?"
    )
    healthcheck_definition = set_else_none(healtheck_keyword, target_definition)
    if isinstance(healthcheck_definition, str):
        port, protocol, ping, health = healthcheck_reg.search(
            healthcheck_definition
        ).groups()
        if not port or not protocol:
            raise ValueError(
                f"You need to define at least the Protocol and port for {healtheck_keyword}"
            )
        healthcheck_props["HealthCheckPort"] = int(port)
        healthcheck_props["HealthCheckProtocol"] = protocol
        if ping:
            handle_ping_settings(healthcheck_props, ping_raw=ping)
        if health:
            try:
                handle_path_settings(healthcheck_props, health)
            except ValueError:
                LOG.error(target_definition["name"], target_definition["healthcheck"])
                raise
    elif isinstance(healthcheck_definition, dict):
        healthcheck_props.update(healthcheck_definition)
        if keyisset("Matcher", healthcheck_definition):
            healthcheck_props["Matcher"] = Matcher(**healthcheck_definition["Matcher"])
    else:
        raise TypeError(
            healthcheck_definition,
            type(healthcheck_definition),
            "must be one of",
            (str, dict),
        )
    props.update(healthcheck_props)


def validate_props_and_service_definition(props: dict, service: ComposeService) -> None:
    """
    Function to validate that the defined settings are valid according to the service definition.
    :raises ValueError: if any of the settings are invalid
    """
    valid_tcp = ["HTTP", "HTTPS", "TLS", "TCP_UDP", "TCP"]
    valid_udp = ["UDP", "TCP_UDP"]
    if not props["Port"] in [p["target"] for p in service.ports]:
        raise ValueError(
            f"Defined TargetGroup port {props['Port']} is not defined for {service.name}."
            " Valid ports are",
            [
                _port["published"]
                for _port in service.ports
                if keyisset("published", _port)
            ],
        )
    chosen_port = [p for p in service.ports if p["target"] == props["Port"]]
    if (chosen_port[0]["protocol"] == "tcp" and props["Protocol"] not in valid_tcp) or (
        chosen_port[0]["protocol"] == "udp" and props["Protocol"] not in valid_udp
    ):
        raise ValueError(
            f"The protocol defined for TargetGroup {props['Protocol']} "
            f"does not match the service protocol {chosen_port[0]['protocol']}"
        )


def handle_sg_lb_ingress_to_service(
    resource, family: ComposeFamily, resources_stack: ComposeXStack
) -> None:
    """
    Function to add ingress from the LB to Target if using ALB
    """
    if resource.is_nlb():
        return
    if resource.cfn_resource and not resource.attributes_outputs:
        resource.init_outputs()
        resource.generate_outputs()
    lb_sg_param = resource.attributes_outputs[LB_SG_ID]["ImportParameter"]
    add_parameters(family.template, [lb_sg_param])
    family.service_networking.add_lb_ingress(
        lb_name=resource.logical_name, lb_sg_ref=Ref(lb_sg_param)
    )
    family.stack.Parameters.update(
        {lb_sg_param.title: resource.attributes_outputs[LB_SG_ID]["ImportValue"]}
    )
    if resources_stack.title not in family.stack.DependsOn:
        family.stack.DependsOn.append(resources_stack.title)


def validate_target_group_attributes(target_attributes, validation, lb_type):
    """
    Function to ensure that each attribute set is compatible with elbv2.type == application

    :param list[TargetGroupAttribute] target_attributes:
    :param dict validation:
    :param str lb_type:
    :raises: ValueError
    """
    for attr in target_attributes:
        if attr.Key not in validation.keys():
            raise ValueError(
                f"Attribute {attr.Key} is not compatible with {lb_type}. Valid ones",
                validation.keys(),
            )
        evaluation = validation[attr.Key]
        if not evaluation(attr.Value):
            raise ValueError(f"{attr.Key} value {attr.Value} is not valid.")


def import_target_group_attributes(props: dict, target_def: dict, elbv2) -> None:
    """Function to do input validation to try avoid incompatible settings together"""
    attributes_key = "TargetGroupAttributes"
    if not keyisset(attributes_key, target_def):
        props[attributes_key] = [
            TargetGroupAttribute(Key="deregistration_delay.timeout_seconds", Value="60")
        ]
    else:
        if isinstance(target_def[attributes_key], list):
            props[attributes_key] = [
                TargetGroupAttribute(Key=attr["Key"], Value=str(attr["Value"]))
                for attr in target_def[attributes_key]
            ]
        elif isinstance(target_def[attributes_key], dict):
            props[attributes_key] = [
                TargetGroupAttribute(Key=key, Value=str(value))
                for key, value in target_def[attributes_key].items()
            ]
    if not keyisset(attributes_key, props):
        props[attributes_key] = [
            TargetGroupAttribute(Key="deregistration_delay.timeout_seconds", Value="60")
        ]
        return
    if "deregistration_delay.timeout_seconds" not in [
        attr.Key for attr in props[attributes_key]
    ]:
        props[attributes_key].append(
            TargetGroupAttribute(Key="deregistration_delay.timeout_seconds", Value="60")
        )
    nlb_valid = {
        "deregistration_delay.connection_termination.enabled": lambda x: x
        in ("true", "false"),
        "preserve_client_ip.enabled": lambda x: x in ("true", "false"),
        "proxy_protocol_v2.enabled": lambda x: x in ("true", "false"),
        "stickiness.type": lambda x: x == "source_ip",
        "deregistration_delay.timeout_seconds": lambda x: 0 <= int(x) <= 3600,
        "stickiness.enabled": lambda x: x in ("true", "false"),
    }
    alb_valid = {
        "stickiness.enabled": lambda x: x in ("true", "false"),
        "stickiness.type": lambda x: x in ("lb_cookie", "app_cookie"),
        "stickiness.app_cookie.cookie_name": lambda x: isinstance(x, str)
        and not re.match(r"^AWSALB.*$|^AWSALBAPP.*|^AWSALBTG.*$", x),
        "stickiness.app_cookie.duration_seconds": lambda x: 1 <= int(x) <= 604800,
        "stickiness.lb_cookie.duration_seconds": lambda x: 1 <= int(x) <= 604800,
        "deregistration_delay.timeout_seconds": lambda x: 0 <= int(x) <= 3600,
        "load_balancing.algorithm.type": lambda x: x
        in ("round_robin", "least_outstanding_requests"),
        "slow_start.duration_seconds": lambda x: 30 <= int(x) <= 900,
    }
    # pragma: ignore use-case for now "lambda.multi_value_headers.enabled": lambda x: x in ("true", "false"),
    if elbv2.lb_type == "application":
        validate_target_group_attributes(
            props[attributes_key], alb_valid, elbv2.lb_type
        )
    if elbv2.lb_type == "network":
        validate_target_group_attributes(
            props[attributes_key], nlb_valid, elbv2.lb_type
        )


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


def setup_template(load_balancer: Elbv2, res_root_stack: ComposeXStack) -> Template:
    """
    Sets up the CloudFormation template for a load balancer by configuring listeners and outputs.

    Args:
        load_balancer (Elbv2): The load balancer resource to configure
        res_root_stack (ComposeXStack): The root stack containing the template

    Returns:
        Template: The configured CloudFormation template with listeners and outputs added

    """
    template: Template = res_root_stack.stack_template
    load_balancer.set_listeners(template)
    load_balancer.associate_to_template(template)
    add_outputs(template, load_balancer.outputs)
    return template


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


def handle_target_groups_association(
    load_balancer: Elbv2, res_root_stack: ComposeXStack, settings: ComposeXSettings
) -> None:
    """
    Function to create TargetGroups based on the `TargetGroups` defined on the ELB rather than the services.
    This allows to associate more than one ECS service to a single TargetGroup.
    """
    template: Template = setup_template(load_balancer, res_root_stack)
    _targets = set_else_none("TargetGroups", load_balancer.definition, {})
    if not _targets:
        return
    for _target_name, _target_def in _targets.items():
        props = {}
        set_healthcheck_definition(props, _target_def, "HealthCheck")
        props["Port"] = _target_def["Port"]
        props["Protocol"] = _target_def["Protocol"]
        props["ProtocolVersion"] = set_else_none(
            "ProtocolVersion", _target_def, Ref(AWS_NO_VALUE)
        )
        props["TargetType"] = "ip"
        import_target_group_attributes(props, _target_def, load_balancer)
        _tgt_group = MergedTargetGroup(
            _target_name,
            _target_def,
            load_balancer,
            load_balancer.stack,
            int(_target_def["Port"]),
            VpcId=Ref(VPC_ID),
            **props,
        )
        _tgt_group.init_outputs()
        _tgt_group.generate_outputs()
        add_resource(template, _tgt_group)
        add_outputs(template, _tgt_group.outputs)
        load_balancer.target_groups.append(_tgt_group)
        _tgt_group.associate_families(settings)

        for listener in load_balancer.new_listeners:
            listener.map_target_group_to_listener(_tgt_group)

        for listener in load_balancer.lookup_listeners.values():
            listener.map_target_group_to_listener(_tgt_group)
    set_target_group_listeners(load_balancer, res_root_stack, template, settings)


def set_target_group_listeners(
    load_balancer: Elbv2,
    res_root_stack: ComposeXStack,
    template: Template,
    settings: ComposeXSettings,
) -> None:

    for listener_port, listener_def in load_balancer.lookup_listeners.items():
        print(listener_port, listener_def)

    for listener in load_balancer.new_listeners:
        listener.handle_certificates(settings, res_root_stack)
        listener.handle_cognito_pools(settings, res_root_stack)
        listener.define_default_actions(load_balancer, template)


def elbv2_to_ecs(
    resources: dict,
    services_stack: ComposeXStack,
    res_root_stack: ComposeXStack,
    settings: ComposeXSettings,
) -> None:
    """
    Entrypoint function to map services, targets, listeners and ACM together.

    Args:
        resources: Dictionary of resources to process
        services_stack: ComposeX stack for services
        res_root_stack: Root ComposeX stack
        settings: ComposeX settings
    """

    def process_resource(resource_name: str, resource, lookup: bool = False) -> None:
        resource_type = "(Lookup)" if lookup else ""
        has_target_groups = keyisset("TargetGroups", resource.definition)

        link_type = "TargetGroups" if has_target_groups else "Services"
        LOG.info(
            f"{resource.module.res_key}.{resource_name} {resource_type} - "
            f"Linking to {link_type}"
        )

        handler = (
            handle_target_groups_association
            if has_target_groups
            else handle_services_association
        )
        handler(resource, res_root_stack, settings)

    for resource_name, resource in resources.items():
        if resource.cfn_resource or resource.mappings:
            process_resource(resource_name, resource, lookup=bool(resource.mappings))
