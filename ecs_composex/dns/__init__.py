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
Package for x-dns
"""

from troposphere import AWS_NO_VALUE
from troposphere import Sub, Ref, Tags, FindInMap, GetAtt
from troposphere.route53 import HostedZone, HostedZoneConfiguration
from troposphere.servicediscovery import (
    PrivateDnsNamespace as VpcSpace,
)

from ecs_composex.common import cfn_params, keyisset, add_parameters, LOG
from ecs_composex.common.aws import get_cross_role_session
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.dns import dns_params, dns_conditions
from ecs_composex.dns.dns_lookup import lookup_namespace


class DnsZone(object):
    """
    Class to represent a zone
    """

    key = None
    nested_name_parameter = None
    nested_id_parameter = None

    def __init__(self, definition):
        """
        Init class
        """
        if not keyisset("Name", definition):
            raise KeyError(
                "You must provide the DNS Name you wish to use for this setting."
            )
        self.root_params = {}
        self.nested_params = {}
        self.dns_mapping = {}
        self.cfn_resource = None
        self.create_zone = False
        self.name_value = Ref(AWS_NO_VALUE)
        self.id_value = Ref(AWS_NO_VALUE)
        self.definition = definition
        self.lookup = (
            self.definition["Lookup"] if keyisset("Lookup", self.definition) else None
        )
        self.use = self.definition["Use"] if keyisset("Use", self.definition) else None
        if self.lookup or self.use:
            self.name_value = FindInMap(
                "Dns", self.key, self.nested_name_parameter.title
            )
            self.id_value = FindInMap("Dns", self.key, self.nested_id_parameter.title)
            self.nested_params.update(
                {
                    self.nested_id_parameter.title: self.id_value,
                    self.nested_name_parameter.title: self.name_value,
                }
            )
        self.name = self.definition["Name"]

    def setup(self, settings):
        if self.lookup:
            self.set_zone_from_lookup(settings)
        elif self.use:
            self.set_zone_from_use()
        else:
            self.create_zone = True
            self.set_zone_default()

    def update_nested_stack_parameters(self, nested_stack):
        """
        Method to updated a nested stack parameters to point to the right value for DNS Settings.

        :param ecs_composex.common.stacks.ComposeXStack nested_stack:
        :return:
        """
        if self.nested_id_parameter.title in nested_stack.stack_template.parameters:
            add_parameters(nested_stack.stack_template, [self.nested_id_parameter])
            nested_stack.Parameters.update(
                {self.nested_id_parameter.title: self.id_value}
            )

        if self.nested_name_parameter.title in nested_stack.stack_template.parameters:
            add_parameters(nested_stack.stack_template, [self.nested_name_parameter])
            nested_stack.Parameters.update(
                {self.nested_name_parameter.title: self.name_value}
            )

    def set_zone_from_lookup(self, settings):
        if keyisset("RoleArn", self.lookup):
            session = get_cross_role_session(
                settings.session, arn=self.lookup["RoleArn"]
            )
        else:
            session = settings.session
        namespace_info = lookup_namespace(self, session)
        if not namespace_info["ZoneTld"].find(self.name) == 0:
            raise ValueError(
                "Zone name provided does not match the value looked up. Got",
                self.name,
                "Resolved via ID",
                namespace_info["ZoneTld"],
            )
        self.dns_mapping.update(
            {
                self.key: {
                    self.nested_name_parameter.title: namespace_info["ZoneTld"],
                    self.nested_id_parameter.title: namespace_info["ZoneId"],
                }
            },
        )
        if hasattr(self, "zone_id_parameter") and keyisset("Route53ID", namespace_info):
            self.dns_mapping[self.key].update(
                {self.zone_id_parameter.title: namespace_info["Route53ID"]}
            )
        self.id_value = FindInMap("Dns", self.key, self.nested_id_parameter.title)
        self.name_value = FindInMap("Dns", self.key, self.nested_name_parameter.title)

    def set_zone_from_use(self):
        """
        Method to create the CFN Mapping for Use on DNS Zone.
        :return:
        """
        self.dns_mapping.update(
            {
                self.key: {
                    self.nested_id_parameter.title: self.use,
                    self.nested_name_parameter.title: self.name,
                }
            }
        )
        self.id_value = FindInMap("Dns", self.key, self.nested_id_parameter.title)
        self.name_value = FindInMap("Dns", self.key, self.nested_name_parameter.title)

    def set_zone_default(self):
        self.dns_mapping.update(
            {self.key: {self.nested_name_parameter.title: self.name}}
        )
        self.nested_params.update(
            {
                self.nested_name_parameter.title: FindInMap(
                    "Dns", self.key, self.nested_name_parameter.title
                ),
            }
        )


class PrivateNamespace(DnsZone):
    """
    Class to handle the private DNS Namespace associated with the VPC used for Service discovery
    """

    key = "PrivateNamespace"
    nested_name_parameter = dns_params.PRIVATE_DNS_ZONE_NAME
    nested_id_parameter = dns_params.PRIVATE_NAMESPACE_ID
    zone_id_parameter = dns_params.PRIVATE_DNS_ZONE_ID

    def __init__(self, definition):
        """
        Init class
        """
        super().__init__(definition)

    def add_zone(self, template, vpc):
        self.cfn_resource = VpcSpace(
            cfn_params.PRIVATE_MAP_TITLE,
            template=template,
            Description=Sub(r"CloudMap VpcNamespace for ${AWS::StackName}"),
            Name=self.name,
            Vpc=vpc,
            DependsOn=[]
            if isinstance(vpc, (FindInMap, Sub, Ref))
            else [cfn_params.VPC_STACK_NAME],
        )
        self.id_value = GetAtt(self.cfn_resource, "Id")
        self.name_value = self.name


class PublicZone(DnsZone):
    """
    Class to represent the Public DNS Zone used for inbound. This is a Route53 DNS Zone.
    """

    key = "PublicZone"
    nested_name_parameter = dns_params.PUBLIC_DNS_ZONE_NAME
    nested_id_parameter = dns_params.PUBLIC_DNS_ZONE_ID

    def __init__(self, definition):
        """"""
        super().__init__(definition)

    def add_zone(self, template):
        self.cfn_resource = HostedZone(
            cfn_params.PUBLIC_ZONE_TITLE,
            Name=self.name,
            template=template,
            HostedZoneTags=Tags(CreatedByComposeX="True", PublicZone="True"),
            HostedZoneConfig=HostedZoneConfiguration(
                Comment=Sub("Public DNS Zone for ${AWS::StackName}")
            ),
        )
        self.id_value = Ref(self.cfn_resource)
        self.name_value = self.name


class DnsSettings(object):
    """
    Class to ingest the x-dns settings
    """

    private_namespace_key = "PrivateNamespace"
    public_namespace_key = "PublicNamespace"
    public_zone_key = "PublicZone"
    supported_keys = [private_namespace_key, public_namespace_key]
    default_private_name = dns_params.PRIVATE_DNS_ZONE_NAME.Default

    def __init__(self, root_stack, settings, vpc):
        """
        Method to initialize DnsSettings class
        :param ecs_composex.common.settings.ComposeXSettings settings: Settings for execution
        """
        self.private_zone_name = dns_params.PRIVATE_DNS_ZONE_NAME.Default
        self.public_zone_name = dns_params.PUBLIC_DNS_ZONE_NAME.Default
        self.public_zone = None
        self.private_zone = None
        self.dns_mapping = {
            PrivateNamespace.key: {
                PrivateNamespace.nested_name_parameter.title: self.default_private_name
            }
        }
        dns_settings = {PrivateNamespace.key: {"Name": self.default_private_name}}

        if keyisset("x-dns", settings.compose_content):
            dns_settings = settings.compose_content["x-dns"]
        if (
            keyisset("x-dns", settings.compose_content)
            and not keyisset(PrivateNamespace.key, settings.compose_content["x-dns"])
            and settings.use_appmesh
        ):
            LOG.warning(
                "You defined to use AppMesh without setting up a PrivateNamespace. Adding a default one."
            )
            dns_settings.update(
                {PrivateNamespace.key: {"Name": self.default_private_name}}
            )

        if keyisset(PrivateNamespace.key, dns_settings):
            self.private_zone = PrivateNamespace(dns_settings[PrivateNamespace.key])
            self.private_zone.setup(settings)
            if self.private_zone.create_zone:
                self.private_zone.add_zone(root_stack.stack_template, vpc)
            self.dns_mapping.update(self.private_zone.dns_mapping)

        if keyisset(PublicZone.key, dns_settings):
            self.public_zone = PublicZone(dns_settings[PublicZone.key])
            self.public_zone.setup(settings)
            if self.public_zone.create_zone:
                self.public_zone.add_zone(root_stack.stack_template)
            self.dns_mapping.update(self.public_zone.dns_mapping)

        if dns_settings:
            root_stack.stack_template.add_mapping("Dns", self.dns_mapping)

    def associate_settings_to_nested_stacks(self, root_stack):
        """
        Method to apply the public and private zone parameters to nested stacks if they needed it.

        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :return:
        """
        for (
            nested_stack_name,
            nested_stack,
        ) in root_stack.stack_template.resources.items():
            if isinstance(nested_stack, ComposeXStack) or issubclass(
                type(nested_stack), ComposeXStack
            ):
                if self.private_zone:
                    self.private_zone.update_nested_stack_parameters(nested_stack)
                if self.public_zone:
                    self.public_zone.update_nested_stack_parameters(nested_stack)
