# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


def validate_tcp_health_counts(props):
    healthy_prop = "HealthyThresholdCount"
    unhealthy_prop = "UnhealthyThresholdCount"
    if (
        keyisset(healthy_prop, props)
        and keyisset(unhealthy_prop, props)
        and not props[unhealthy_prop] == props[healthy_prop]
    ):
        valid_value = max(props[unhealthy_prop], props[healthy_prop])
        LOG.warning(
            "With NLB your healthy and unhealthy count must be the same. Using the max of the two for cautious: "
            f"{valid_value}"
        )
        props[healthy_prop] = valid_value
        props[unhealthy_prop] = valid_value


def fix_nlb_settings(props):
    """
    Function to automatically adjust/correct settings for NLB to avoid users cringe on fails

    :param dict props:
    """
    network_modes = ["TCP", "UDP", "TCP_UDP"]
    if (
        keyisset("HealthCheckProtocol", props)
        and not props["HealthCheckProtocol"] in network_modes
    ):
        return
    if keyisset("HealthCheckTimeoutSeconds", props):
        LOG.warning("With NLB you cannot set intervals. Resetting")
        props["HealthCheckTimeoutSeconds"] = Ref(AWS_NO_VALUE)
    if (
        keyisset("HealthCheckIntervalSeconds", props)
        and not (
            props["HealthCheckIntervalSeconds"] == 10
            or props["HealthCheckIntervalSeconds"] == 30
        )
        and not isinstance(props["HealthCheckIntervalSeconds"], Ref)
    ):
        right_value = min(
            [10, 30], key=lambda x: abs(x - props["HealthCheckIntervalSeconds"])
        )
        LOG.warning(
            f"Set to {props['HealthCheckIntervalSeconds']} - "
            f"The only intervals value valid for NLB are 10 and 30. Closest value is {right_value}"
        )
        props["HealthCheckIntervalSeconds"] = right_value
    validate_tcp_health_counts(props)


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
        ("HealthCheckIntervalSeconds", (2, 120)),
        ("HealthCheckTimeoutSeconds", (2, 10)),
    )
    for count, value in enumerate(groups):
        if not min(ping_mapping[count][1]) <= int(value) <= max(ping_mapping[count][1]):
            LOG.error(
                f"Value for {ping_mapping[count][0]} is not valid. Must be in range of {ping_mapping[count][1]}"
            )
        props[ping_mapping[count][0]] = int(value)
    fix_nlb_settings(props)


def handle_path_settings(props, path_raw):
    """
    Function to set the path and codes properties

    :param dict props:
    :param str path_raw:
    :return:
    """
    path_re = re.compile(
        r"(/[\S][^:]+.$)|(/[\S]+)(?::)((?:[\d]{1,4},?){1,}.$)|((?:[\d]{1,4},?){1,}.$)"
    )
    groups = path_re.search(path_raw).groups()
    if not groups:
        LOG.debug("No PATH or ReturnCodes set.")
        return
    path = groups[0] or groups[1]
    codes = groups[2] or groups[3]
    if path:
        props["HealthCheckPath"] = path
    if codes:
        props["Matcher"] = Matcher(HttpCode=codes)
    if props["HealthCheckProtocol"] not in ["HTTP", "HTTPS"] and codes:
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
    required_mapping = (
        "HealthCheckPort",
        "HealthCheckProtocol",
    )
    required_rex = re.compile(r"^([\d]{2,5}):(HTTPS|HTTP|TCP_UDP|TCP|TLS|UDP)$")
    healthcheck_reg = re.compile(
        r"(^(?:[\d]{2,5}):(?:HTTPS|HTTP|TCP_UDP|TCP|TLS|UDP)):?"
        r"((?:[\d]{1}|10):(?:[\d]{1}|10):[\d]{1,3}:[\d]{1,3})?:"
        r"?((?:/[\S][^:]+.$)|(?:/[\S]+)(?::)(?:(?:[\d]{1,4},?){1,}.$)|(?:(?:[\d]{1,4},?){1,}.$))?"
    )
    healthcheck_definition = set_else_none(healtheck_keyword, target_definition)
    if isinstance(healthcheck_definition, str):
        groups = healthcheck_reg.search(healthcheck_definition).groups()
        if not groups[0]:
            raise ValueError(
                f"You need to define at least the Protocol and port for {healtheck_keyword}"
            )
        for count, value in enumerate(required_rex.match(groups[0]).groups()):
            healthcheck_props[required_mapping[count]] = value
        if groups[1]:
            handle_ping_settings(healthcheck_props, groups[1])
        if groups[2]:
            try:
                handle_path_settings(healthcheck_props, groups[2])
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


def validate_props_and_service_definition(props, service):
    """
    Function to validate that the defined settings are valid according to the service definition.
    :param props:
    :param ecs_composex.common.compose_services.ComposeService service:
    :return:
    """
    valid_tcp = ["HTTP", "HTTPS", "TLS", "TCP_UDP", "TCP"]
    valid_udp = ["UDP", "TCP_UDP"]
    if not props["Port"] in [p["target"] for p in service.ports]:
        raise ValueError(
            f"Defined TargetGroup port {props['Port']} is not defined for {service.name}."
            " Valid ports are",
            [p["published"] for p in service.ports],
        )
    chosen_port = [p for p in service.ports if p["target"] == props["Port"]]
    if (chosen_port[0]["protocol"] == "tcp" and props["Protocol"] not in valid_tcp) or (
        chosen_port[0]["protocol"] == "udp" and props["Protocol"] not in valid_udp
    ):
        raise ValueError(
            f"The protocol defined for TargetGroup {props['Protocol']} "
            f"does not match the service protocol {chosen_port[0]['protocol']}"
        )


def handle_sg_lb_ingress_to_service(resource, family, resources_stack):
    """
    Function to add ingress from the LB to Target if using ALB
    :param resource:
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param resources_stack:
    :return:
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


def import_target_group_attributes(props, target_def, elbv2):
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
    if elbv2.cfn_resource.Type == "application":
        validate_target_group_attributes(
            props[attributes_key], alb_valid, elbv2.cfn_resource.Type
        )
    if elbv2.cfn_resource.Type == "network":
        validate_target_group_attributes(
            props[attributes_key], nlb_valid, elbv2.cfn_resource.Type
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
    fix_nlb_settings(props)
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


def handle_services_association(
    load_balancer: Elbv2, res_root_stack: ComposeXStack, settings: ComposeXSettings
) -> None:
    """
    Function to handle association of listeners and targets to the LB
    """
    template = res_root_stack.stack_template
    load_balancer.set_listeners(template)
    load_balancer.associate_to_template(template)
    add_outputs(template, load_balancer.outputs)
    identified = []
    for target in load_balancer.families_targets:
        if target[1].launch_type == "EXTERNAL":
            LOG.error(
                f"x-elbv2.{load_balancer.name} - Target family {target[0].name} uses EXTERNAL launch type. Ignoring"
            )
            continue
        tgt_group = define_service_target_group_definition(
            load_balancer, target[0], target[1], target[2], res_root_stack
        )
        for service in load_balancer.services:
            target_name = f"{target[0].name}:{target[1].name}"
            if target_name not in service["name"]:
                continue
            if target_name == service["name"] and tgt_group.Port == int(
                service["port"]
            ):
                service["target_arn"] = Ref(tgt_group)
                identified.append(True)
                break

    if not identified:
        LOG.error(
            f"{load_balancer.module.res_key}.{load_balancer.name} - No services found as targets. Skipping association"
        )
        return

    for listener in load_balancer.listeners:
        listener.map_lb_target_groups_service_to_listener_targets(load_balancer)

    for listener in load_balancer.listeners:
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
    template = res_root_stack.stack_template
    load_balancer.set_listeners(template)
    load_balancer.associate_to_template(template)
    add_outputs(template, load_balancer.outputs)
    _targets = set_else_none("TargetGroups", load_balancer.definition, {})
    if not _targets:
        return
    for _target_name, _target_def in _targets.items():
        props = {}
        set_healthcheck_definition(props, _target_def, "HealthCheck")
        props["Port"] = _target_def["Port"]
        props["Protocol"] = _target_def["Protocol"]
        fix_nlb_settings(props)
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

        for listener in load_balancer.listeners:
            listener.map_target_group_to_listener(_tgt_group)

    for listener in load_balancer.listeners:
        listener.handle_certificates(settings, res_root_stack)
        listener.handle_cognito_pools(settings, res_root_stack)
        listener.define_default_actions(load_balancer, template)


def elbv2_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Entrypoint function to map services, targets, listeners and ACM together

    :param dict resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for resource_name, resource in resources.items():
        if resource.cfn_resource and not resource.mappings:
            if keyisset("TargetGroups", resource.definition):
                LOG.info(
                    f"{resource.module.res_key}.{resource_name} - Linking to TargetGroups"
                )
                handle_target_groups_association(resource, res_root_stack, settings)
            else:
                LOG.info(
                    f"{resource.module.res_key}.{resource_name} - Linking to Services"
                )
                handle_services_association(resource, res_root_stack, settings)
