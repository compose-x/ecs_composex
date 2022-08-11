#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.mods_manager import XResourceModule
    from ecs_composex.common.settings import ComposeXSettings

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import AWS_NO_VALUE, AWS_STACK_NAME, GetAtt, Ref, Select, Sub, Tags
from troposphere.ec2 import EIP, SecurityGroup
from troposphere.elasticloadbalancingv2 import (
    LoadBalancer,
    LoadBalancerAttributes,
    SubnetMapping,
)

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import ROOT_STACK_NAME
from ecs_composex.compose.x_resources.network_x_resources import NetworkXResource
from ecs_composex.elbv2.elbv2_params import (
    LB_DNS_NAME,
    LB_DNS_ZONE_ID,
    LB_FULL_NAME,
    LB_NAME,
    LB_SG_ID,
    MOD_KEY,
)
from ecs_composex.elbv2.elbv2_stack.elbv2_listener import ComposeListener
from ecs_composex.elbv2.elbv2_stack.helpers import (
    handle_cross_zone,
    handle_desync_mitigation_mode,
    handle_drop_invalid_headers,
    handle_http2,
    handle_timeout_seconds,
    validate_listeners_duplicates,
)
from ecs_composex.ingress_settings import Ingress, set_service_ports
from ecs_composex.vpc.vpc_params import APP_SUBNETS, PUBLIC_SUBNETS, VPC_ID


class Elbv2(NetworkXResource):
    """
    Class to handle ELBv2 creation and mapping to ECS Services
    """

    subnets_param = APP_SUBNETS

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        if not keyisset("Listeners", definition):
            raise KeyError("You must specify at least one Listener for a LB.", name)
        self.lb_is_public = False
        self.lb_type = "application"
        self.ingress = None
        self.lb_sg = None
        self.lb_eips = []
        self.unique_service_lb = False
        self.lb = None
        self.listeners = []
        super().__init__(name, definition, module, settings)
        self.validate_services()
        self.sort_props()
        self.module_name = MOD_KEY

    def init_outputs(self):
        self.output_properties = {
            LB_DNS_NAME: (
                f"{self.logical_name}{LB_DNS_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                LB_DNS_NAME.return_value,
            ),
            LB_DNS_ZONE_ID: (
                f"{self.logical_name}{LB_DNS_ZONE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                LB_DNS_ZONE_ID.return_value,
            ),
            LB_NAME: (
                f"{self.logical_name}{LB_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                LB_NAME.return_value,
            ),
            LB_FULL_NAME: (
                f"{self.logical_name}{LB_FULL_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                LB_FULL_NAME.return_value,
            ),
        }

    def set_listeners(self, template):
        """
        Method to define the listeners
        :return:
        """
        if not keyisset("Listeners", self.definition):
            raise KeyError(f"You must define at least one listener for LB {self.name}")
        ports = [listener["Port"] for listener in self.definition["Listeners"]]
        validate_listeners_duplicates(self.name, ports)
        for listener_def in self.definition["Listeners"]:
            if keyisset("Targets", listener_def):
                for target in listener_def["Targets"]:
                    if target["name"] not in [svc["name"] for svc in self.services]:
                        listener_def["Targets"].remove(target)
            if keyisset("Targets", listener_def) or keyisset(
                "DefaultActions", listener_def
            ):
                new_listener = template.add_resource(
                    ComposeListener(self, listener_def)
                )
                self.listeners.append(new_listener)
            else:
                LOG.warning(
                    f"{self.module.res_key}.{self.name} - "
                    f"Listener {listener_def['Port']} has no action or service. Not used."
                )

    def set_services_targets(self, settings):
        """
        Method to map services and families targets of the services defined.
        TargetStructure:
        (family, family_wide, services[], access)

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if not self.services:
            LOG.debug(f"{self.module.res_key}.{self.name} No Services defined.")
            return
        for service_def in self.services:
            family_combo_name = service_def["name"]
            service_name = family_combo_name.split(":")[-1]
            family_name = NONALPHANUM.sub("", family_combo_name.split(":")[0])
            LOG.info(
                f"{self.module.res_key}.{self.name} - Adding target {family_name}:{service_name}"
            )
            if family_name not in settings.families:
                raise ValueError(
                    f"{self.module.res_key}.{self.name} - Service family {family_name} is invalid. Defined families",
                    settings.families.keys(),
                )
            for f_service in settings.families[family_name].ordered_services:
                if f_service.name == service_name:
                    if f_service not in settings.services:
                        raise ValueError(
                            f"{self.module.res_key}.{self.name} Please, use only the services names."
                            "You cannot use the family name defined by deploy labels"
                            f"Found {f_service}",
                            [s for s in settings.services],
                            [f for f in settings.families],
                        )
                    elif (
                        f_service.name == service_name
                        and f_service in settings.services
                        and f_service not in self.families_targets
                    ):
                        self.families_targets.append(
                            (
                                f_service.family,
                                f_service,
                                service_def,
                                f"{service_def['name']}{service_def['port']}",
                            )
                        )
                        break
            else:
                raise ValueError(
                    f"{self.module.res_key}.{self.name} - Could not find {service_name} in family {family_name}"
                )

        self.debug_families_targets()

    def validate_services(self):
        services_names = list({service["name"] for service in self.services})
        if len(services_names) == 1:
            LOG.info(
                f"LB {self.name} only has a unique service. LB will be deployed with the service stack."
            )
            self.unique_service_lb = True

    def sort_props(self):
        self.lb_is_public = (
            True
            if (
                keyisset("Scheme", self.properties)
                and self.properties["Scheme"] == "internet-facing"
            )
            else False
        )
        self.lb_type = (
            "application"
            if not keyisset("Type", self.properties)
            else self.properties["Type"]
        )
        self.sort_sg()

    def sort_sg(self):
        if self.is_nlb():
            self.lb_sg = Ref(AWS_NO_VALUE)
        elif self.is_alb():
            self.lb_sg = SecurityGroup(
                f"{self.logical_name}SecurityGroup",
                GroupDescription=Sub(
                    f"SG for LB {self.logical_name} in ${{{AWS_STACK_NAME}}}"
                ),
                GroupName=Sub(
                    f"{self.logical_name}-{self.lb_type}-sg-${{{AWS_STACK_NAME}}}"
                ),
                VpcId=Ref(VPC_ID),
                Tags=Tags(Name=Sub(f"elbv2-{self.logical_name}-${{{AWS_STACK_NAME}}}")),
            )

    def sort_alb_ingress(self, settings, stack_template):
        """
        Method to handle Ingress to ALB
        """
        if (
            not self.parameters
            or (self.parameters and not keyisset("Ingress", self.parameters))
            or self.is_nlb()
        ):
            LOG.warning(
                "You defined ingress rules for a NLB. This is invalid. Define ingress rules at the service level."
            )
            return
        elif not self.parameters or (
            self.parameters and not keyisset("Ingress", self.parameters)
        ):
            LOG.warning(f"You did not define any Ingress rules for ALB {self.name}.")
            return
        ports = [listener["Port"] for listener in self.definition["Listeners"]]
        ports = set_service_ports(ports)
        self.ingress = Ingress(self.parameters["Ingress"], ports)
        if self.ingress and self.is_alb():
            self.ingress.set_aws_sources_ingress(
                settings, self.logical_name, GetAtt(self.lb_sg, "GroupId")
            )
            self.ingress.set_ext_sources_ingress(
                self.logical_name, GetAtt(self.lb_sg, "GroupId")
            )
            self.ingress.associate_aws_ingress_rules(stack_template)
            self.ingress.associate_ext_ingress_rules(stack_template)

    def define_override_subnets(self, subnets, vpc_stack):
        """
        Method to define the subnets overrides to use for the LB

        :param subnets: The original subnets to replace
        :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack:
        :return: the subnet name to use
        :rtype: str
        """
        if self.subnets_override:
            if self.subnets_override not in vpc_stack.vpc_resource.mappings.keys():
                raise KeyError(
                    f"The subnets indicated for {self.name} is not valid. Valid ones are",
                    vpc_stack.vpc_resource.mappings.keys(),
                )
            return self.subnets_override
        if isinstance(subnets, Ref):
            return subnets.data["Ref"]
        return subnets

    def set_eips(self, vpc_stack):
        """

        :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack:
        :return:
        """
        if self.is_nlb() and self.lb_is_public:
            if vpc_stack.vpc_resource.cfn_resource:
                for public_subnet in vpc_stack.vpc_resource.public_subnets[1]:
                    self.lb_eips.append(
                        EIP(
                            f"{self.logical_name}Eip{public_subnet.title}",
                            Domain="vpc",
                        )
                    )
            elif vpc_stack.vpc_resource.mappings:
                subnets = self.define_override_subnets(PUBLIC_SUBNETS.title, vpc_stack)
                for public_az in vpc_stack.vpc_resource.mappings[subnets]["Azs"]:
                    self.lb_eips.append(
                        EIP(
                            f"{self.logical_name}Eip{public_az.title().split('-')[-1]}",
                            Domain="vpc",
                        )
                    )

    def set_subnets(self, vpc_stack):
        """
        Method to define which subnets to use for the

        :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack:
        :return:
        """
        if self.is_nlb():
            return Ref(AWS_NO_VALUE)
        elif not self.lb_is_public and self.subnets_override:
            if vpc_stack.vpc_resource.cfn_resource and self.subnets_override not in [
                PUBLIC_SUBNETS.title,
                APP_SUBNETS.title,
            ]:
                raise ValueError(
                    "When Compose-X creates the VPC, the only subnets you can define to use are",
                    [PUBLIC_SUBNETS.title, APP_SUBNETS.title],
                )
            elif (
                not vpc_stack.vpc_resource.cfn_resource
                and vpc_stack.vpc_resource.mappings
                and self.subnets_override in vpc_stack.vpc_resource.mappings.keys()
            ):
                return Ref(self.subnets_override)
        else:
            if self.is_alb() and self.lb_is_public:
                return Ref(PUBLIC_SUBNETS)
            elif not self.lb_is_public:
                return Ref(APP_SUBNETS)
        return APP_SUBNETS.title

    def set_subnet_mappings(self, vpc_stack):
        """
        For NLB, defines the EC2 EIP and Subnets Mappings to use.
        Determines the number of EIP to produce from the VPC Settings.
        """
        if self.is_alb():
            return Ref(AWS_NO_VALUE)
        if not self.lb_eips and self.lb_is_public:
            self.set_eips(vpc_stack)
        mappings = []
        subnets = self.define_override_subnets(PUBLIC_SUBNETS.title, vpc_stack)
        for count, eip in enumerate(self.lb_eips):
            mappings.append(
                SubnetMapping(
                    AllocationId=GetAtt(eip, "AllocationId"),
                    SubnetId=Select(count, Ref(subnets)),
                )
            )
        return mappings

    def parse_attributes_settings(self):
        """
        Method to parse pre-defined settings for shortcuts

        :return: the lb attributes mappings
        :rtype: list
        """
        valid_settings = [
            ("timeout_seconds", int, handle_timeout_seconds, self.is_alb()),
            (
                "desync_mitigation_mode",
                str,
                handle_desync_mitigation_mode,
                self.is_alb(),
            ),
            (
                "drop_invalid_header_fields",
                bool,
                handle_drop_invalid_headers,
                self.is_alb(),
            ),
            ("http2", bool, handle_http2, self.is_alb()),
            ("cross_zone", bool, handle_cross_zone, self.is_nlb()),
        ]
        mappings = []
        for setting in valid_settings:
            if (
                keypresent(setting[0], self.parameters)
                and isinstance(self.parameters[setting[0]], setting[1])
                and setting[3]
            ):
                if setting[2] and setting[3]:
                    mappings.append(setting[2](self.parameters[setting[0]]))
                elif setting[3]:
                    mappings.append(
                        LoadBalancerAttributes(
                            Key=setting[0],
                            Value=str(self.parameters[setting[0]]),
                        )
                    )
        return mappings

    def set_lb_attributes(self):
        """
        Method to define the LB attributes

        :return: List of LB Attributes
        :rtype: list
        """
        attributes = []
        if keyisset("LoadBalancerAttributes", self.properties):
            for prop in self.properties["LoadBalancerAttributes"]:
                attributes.append(
                    LoadBalancerAttributes(
                        Key=prop,
                        Value=self.properties["LoadBalancerAttributes"][prop],
                    )
                )
        elif (
            not keyisset("LoadBalancerAttributes", self.definition) and self.parameters
        ):
            attributes = self.parse_attributes_settings()
        if attributes:
            return attributes
        return Ref(AWS_NO_VALUE)

    def set_lb_definition(self):
        """
        Function to parse the LB settings and properties and build the LB object

        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        attrs = {
            "IpAddressType": "ipv4"
            if not keyisset("IpAddressType", self.properties)
            else self.properties["IpAddressType"],
            "Type": self.lb_type,
            "Scheme": "internet-facing" if self.lb_is_public else "internal",
            "SecurityGroups": [Ref(self.lb_sg)]
            if isinstance(self.lb_sg, SecurityGroup)
            else self.lb_sg,
            "Subnets": Ref(AWS_NO_VALUE),
            "SubnetMappings": Ref(AWS_NO_VALUE),
            "LoadBalancerAttributes": self.set_lb_attributes(),
            "Tags": Tags(Name=Sub(f"${{{ROOT_STACK_NAME.title}}}{self.logical_name}")),
            "Name": Ref(AWS_NO_VALUE),
        }
        self.lb = LoadBalancer(self.logical_name, **attrs)
        self.cfn_resource = self.lb

    def is_nlb(self):
        return True if self.lb_type == "network" else False

    def is_alb(self):
        return True if self.lb_type == "application" else False

    def associate_to_template(self, template):
        """
        Method to associate all resources to the template

        :param troposphere.Template template:
        :return:
        """
        template.add_resource(self.lb)
        self.init_outputs()
        if self.lb_sg and isinstance(self.lb_sg, SecurityGroup):
            self.output_properties.update(
                {
                    LB_SG_ID: (
                        f"{self.logical_name}{LB_SG_ID.return_value}",
                        self.lb_sg,
                        GetAtt,
                        LB_SG_ID.return_value,
                        None,
                    )
                }
            )
            template.add_resource(self.lb_sg)
        for eip in self.lb_eips:
            template.add_resource(eip)
        self.generate_outputs()

    def update_from_vpc(self, vpc_stack, settings=None):
        """
        Override to set the specific resources right once we have a VPC Definition

        :param ecs_composex.vpc.vpc_stack.VpcStack vpc_stack:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        if vpc_stack and vpc_stack.vpc_resource:
            if self.is_alb():
                self.cfn_resource.Subnets = self.set_subnets(vpc_stack)
            elif self.is_nlb():
                self.cfn_resource.SubnetMappings = self.set_subnet_mappings(vpc_stack)
