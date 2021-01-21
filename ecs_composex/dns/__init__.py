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

from troposphere import Sub, Ref, GetAtt, If, Tags, FindInMap
from troposphere.servicediscovery import (
    PrivateDnsNamespace as VpcSpace,
    PublicDnsNamespace as PublicSpace,
)
from troposphere.route53 import HostedZone, HostedZoneConfiguration

from ecs_composex.common import cfn_params, keyisset, add_parameters, LOG
from ecs_composex.dns import dns_params, dns_conditions
from ecs_composex.dns.dns_lookup import lookup_namespace


def add_parameters_and_conditions(root_stack, settings):
    """
    Adds parameters and conditions to the root stack
    :param root_stack:
    :return:
    """
    if settings.for_cfn_macro:
        return
    add_parameters(
        root_stack.stack_template,
        [
            dns_params.PUBLIC_DNS_ZONE_ID,
            dns_params.PUBLIC_DNS_ZONE_NAME,
            dns_params.PRIVATE_DNS_ZONE_ID,
            dns_params.PRIVATE_DNS_ZONE_NAME,
        ],
    )
    root_stack.stack_template.add_condition(
        dns_conditions.USE_DEFAULT_ZONE_NAME_CON_T,
        dns_conditions.USE_DEFAULT_ZONE_NAME_CON,
    )
    root_stack.stack_template.add_condition(
        dns_conditions.CREATE_PRIVATE_NAMESPACE_CON_T,
        dns_conditions.CREATE_PRIVATE_NAMESPACE_CON,
    )
    root_stack.stack_template.add_condition(
        dns_conditions.CREATE_PUBLIC_NAMESPACE_CON_T,
        dns_conditions.CREATE_PUBLIC_NAMESPACE_CON,
    )
    root_stack.stack_template.add_condition(
        dns_conditions.CREATE_PUBLIC_ZONE_CON_T, dns_conditions.CREATE_PUBLIC_ZONE_CON
    )


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
        self.root_params = {}
        self.nested_params = {}
        self.public_map = None
        self.public_zone = None
        self.create_public_zone = True
        self.dns_mapping = {
            "PrivateNamespace": {
                dns_params.PRIVATE_DNS_ZONE_NAME.title: self.private_zone_name
            }
        }
        self.private_map = None

        if not keyisset("x-dns", settings.compose_content) and settings.use_appmesh:
            dns_settings = {
                self.private_namespace_key: {"Name": self.default_private_name}
            }
        else:
            dns_settings = settings.compose_content["x-dns"]

        if keyisset(self.private_namespace_key, dns_settings):
            self.add_private_namespace(settings, dns_settings, root_stack, vpc)

        if keyisset(self.public_zone_key, dns_settings):
            self.add_public_zone(settings, dns_settings, root_stack)
        # elif keyisset(self.public_namespace_key, dns_settings):
        #     self.add_public_namespace(settings, dns_settings, root_stack)
        root_stack.stack_template.add_mapping("Dns", self.dns_mapping)

    def add_private_namespace_resource(self, root_stack, vpc, name=None):
        self.private_map = VpcSpace(
            cfn_params.PRIVATE_MAP_TITLE,
            template=root_stack.stack_template,
            Description=Sub(r"CloudMap VpcNamespace for ${AWS::StackName}"),
            Name=Sub("${AWS::StackName}.internal") if not name else name,
            Vpc=vpc,
            DependsOn=[] if isinstance(vpc, Ref) else [cfn_params.VPC_STACK_NAME],
        )

    def add_private_namespace(self, settings, dns_settings, root_stack, vpc):
        """
        Add private zone to root template

        :return:
        """
        if keyisset("Lookup", dns_settings[self.private_namespace_key]):
            namespace_info = lookup_namespace(
                dns_settings[self.private_namespace_key]["Lookup"],
                settings.session,
                private=True,
            )
            if not namespace_info:
                raise LookupError("Failed to retrieve namespace information")
            if not settings.for_cfn_macro:
                self.private_zone_name = namespace_info["ZoneTld"]
                self.root_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: namespace_info[
                            "ZoneTld"
                        ],
                        dns_params.PRIVATE_DNS_ZONE_ID.title: namespace_info[
                            "NamespaceId"
                        ],
                    }
                )
                self.nested_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: dns_params.DEFAULT_PRIVATE_DNS_ZONE,
                        dns_params.PRIVATE_DNS_ZONE_ID.title: dns_params.PRIVATE_DNS_ZONE_ID,
                    }
                )
            else:
                self.dns_mapping.update(
                    {
                        "PrivateNamespace": {
                            dns_params.PRIVATE_DNS_ZONE_NAME.title: namespace_info[
                                "ZoneTld"
                            ],
                            dns_params.PRIVATE_DNS_ZONE_ID.title: namespace_info[
                                "NamespaceId"
                            ],
                        }
                    }
                )
                self.nested_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: FindInMap(
                            "Dns",
                            "PrivateNamespace",
                            dns_params.PRIVATE_DNS_ZONE_NAME.title,
                        ),
                        dns_params.PRIVATE_DNS_ZONE_ID: FindInMap(
                            "Dns",
                            "PrivateNamespace",
                            dns_params.PRIVATE_DNS_ZONE_ID.title,
                        ),
                    }
                )
        elif keyisset("Use", dns_settings[self.private_namespace_key]):
            if not settings.for_cfn_macro:
                self.root_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_ID.title: dns_settings[
                            self.private_namespace_key
                        ]["Use"],
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: self.private_zone_name,
                    }
                )
                self.nested_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_ID.title: If(
                            dns_conditions.CREATE_PRIVATE_NAMESPACE_CON_T,
                            GetAtt(self.private_map, "Id"),
                            Ref(dns_params.PRIVATE_DNS_ZONE_ID),
                        ),
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: dns_params.DEFAULT_PRIVATE_DNS_ZONE,
                    }
                )
            else:
                self.dns_mapping.update(
                    {
                        "PrivateNamespace": {
                            {
                                dns_params.PRIVATE_DNS_ZONE_ID.title: dns_settings[
                                    self.private_namespace_key
                                ]["Use"],
                                dns_params.PRIVATE_DNS_ZONE_NAME.title: self.private_zone_name,
                            }
                        }
                    }
                )
                self.nested_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_ID.title: FindInMap(
                            "Dns",
                            "PrivateNamespace",
                            dns_params.PRIVATE_DNS_ZONE_ID.title,
                        ),
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: FindInMap(
                            "Dns",
                            "PrivateNamespace",
                            dns_params.PRIVATE_DNS_ZONE_NAME.title,
                        ),
                    }
                )
        else:
            if not settings.use_appmesh and not keyisset(
                "Name", dns_settings[self.private_namespace_key]
            ):
                return
            elif keyisset("Name", dns_settings[self.private_namespace_key]):
                self.private_zone_name = dns_settings[self.private_namespace_key][
                    "Name"
                ]
            else:
                self.private_zone_name = dns_params.PRIVATE_DNS_ZONE_NAME.Default
            if not self.private_map:
                self.add_private_namespace_resource(
                    root_stack, vpc, name=self.private_zone_name
                )
                self.nested_params.update(
                    {
                        dns_params.PRIVATE_DNS_ZONE_NAME.title: self.private_zone_name,
                        dns_params.PRIVATE_DNS_ZONE_ID.title: GetAtt(
                            self.private_map, "Id"
                        ),
                    }
                )

    # def add_public_namespace(self, settings, dns_settings, root_stack):
    #     """
    #
    #     :return:
    #     """
    #     self.public_map = PublicSpace(
    #         cfn_params.PUBLIC_MAP_TITLE,
    #         template=root_stack.stack_template,
    #         Condition=dns_conditions.CREATE_PUBLIC_NAMESPACE_CON_T,
    #         Description=Sub(r"Public DnsNamespace for ${AWS::StackName}"),
    #         Name=dns_params.DEFAULT_PUBLIC_DNS_ZONE,
    #     )
    #
    #     if keyisset("Name", dns_settings[self.public_namespace_key]):
    #         self.public_zone_name = dns_settings[self.public_namespace_key]["Name"]
    #
    #     if keyisset("Lookup", dns_settings[self.public_namespace_key]):
    #         namespace_info = lookup_namespace(
    #             dns_settings[self.public_namespace_key]["Lookup"],
    #             settings.session,
    #             private=False,
    #         )
    #         if not namespace_info["ZoneTld"].find(self.public_zone_name) == 0:
    #             raise ValueError(
    #                 "Zone name provided does not match the value looked up. Got",
    #                 self.public_zone_name,
    #                 "Resolved via ID",
    #                 namespace_info["ZoneTld"],
    #             )
    #         self.root_params.update(
    #             {
    #                 dns_params.PUBLIC_DNS_ZONE_NAME.title: namespace_info["ZoneTld"],
    #                 dns_params.PUBLIC_DNS_ZONE_ID.title: namespace_info["ZoneId"],
    #             }
    #         )
    #         self.nested_params.update(
    #             {
    #                 dns_params.PUBLIC_DNS_ZONE_NAME: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
    #                 dns_params.PUBLIC_DNS_ZONE_ID.title: Ref(
    #                     dns_params.PUBLIC_DNS_ZONE_ID
    #                 ),
    #             }
    #         )
    #     else:
    #         self.root_params.update(
    #             {dns_params.PUBLIC_DNS_ZONE_NAME.title: self.public_zone_name}
    #         )
    #         self.nested_params.update(
    #             {
    #                 dns_params.PUBLIC_DNS_ZONE_NAME.title: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
    #                 dns_params.PUBLIC_DNS_ZONE_ID.title: GetAtt(self.public_map, "Id"),
    #             }
    #         )

    def set_public_zone_lookup_params(self, settings, dns_settings, root_stack):
        self.create_public_zone = False
        namespace_info = lookup_namespace(
            dns_settings[self.public_zone_key]["Lookup"],
            settings.session,
            private=False,
        )
        if not namespace_info["ZoneTld"].find(self.public_zone_name) == 0:
            raise ValueError(
                "Zone name provided does not match the value looked up. Got",
                self.public_zone_name,
                "Resolved via ID",
                namespace_info["ZoneTld"],
            )
        if not settings.for_cfn_macro:
            self.root_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: namespace_info["ZoneTld"],
                    dns_params.PUBLIC_DNS_ZONE_ID.title: namespace_info["ZoneId"],
                }
            )
            self.nested_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_NAME: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
                    dns_params.PUBLIC_DNS_ZONE_ID.title: Ref(
                        dns_params.PUBLIC_DNS_ZONE_ID
                    ),
                }
            )
        else:
            self.dns_mapping.update(
                {
                    "PublicZone": {
                        dns_params.PUBLIC_DNS_ZONE_NAME.title: namespace_info[
                            "ZoneTld"
                        ],
                        dns_params.PUBLIC_DNS_ZONE_ID.title: namespace_info["ZoneId"],
                    }
                },
            )
            self.nested_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_ID.title: FindInMap(
                        "Dns", "PublicZone", dns_params.PUBLIC_DNS_ZONE_ID.title
                    ),
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: FindInMap(
                        "Dns", "PublicZone", dns_params.PUBLIC_DNS_ZONE_NAME.title
                    ),
                }
            )

    def set_public_zone_default_params(self, settings, root_stack):
        if settings.for_cfn_macro:
            self.root_params.update(
                {dns_params.PUBLIC_DNS_ZONE_NAME.title: self.public_zone_name}
            )
            self.nested_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
                    dns_params.PUBLIC_DNS_ZONE_ID.title: Ref(self.public_zone),
                }
            )
        else:
            self.dns_mapping.update(
                {
                    "PublicZone": {
                        dns_params.PUBLIC_DNS_ZONE_NAME.title: self.public_zone_name
                    }
                },
            )
            self.nested_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
                    dns_params.PUBLIC_DNS_ZONE_ID.title: FindInMap(
                        "Dns", "PublicZone", dns_params.PUBLIC_DNS_ZONE_NAME.title
                    ),
                }
            )

    def set_public_zone_use_params(self, settings, dns_settings):
        self.create_public_zone = False
        if not settings.for_cfn_macro:
            self.root_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_ID.title: dns_settings[
                        self.public_zone_key
                    ]["Use"],
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: self.public_zone_name,
                }
            )
            self.nested_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_ID.title: If(
                        dns_conditions.CREATE_PUBLIC_ZONE_CON_T,
                        Ref(self.public_zone),
                        Ref(dns_params.PUBLIC_DNS_ZONE_ID),
                    ),
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
                }
            )
        else:
            self.dns_mapping.update(
                {
                    "PublicZone": {
                        {
                            dns_params.PUBLIC_DNS_ZONE_ID.title: dns_settings[
                                self.public_zone_key
                            ]["Use"],
                            dns_params.PUBLIC_DNS_ZONE_NAME.title: self.public_zone_name,
                        }
                    }
                }
            )
            self.nested_params.update(
                {
                    dns_params.PUBLIC_DNS_ZONE_ID.title: FindInMap(
                        "Dns", "PublicZone", dns_params.PUBLIC_DNS_ZONE_ID.title
                    ),
                    dns_params.PUBLIC_DNS_ZONE_NAME.title: dns_params.DEFAULT_PUBLIC_DNS_ZONE,
                }
            )

    def add_public_zone(self, settings, dns_settings, root_stack):
        self.public_zone = HostedZone(
            cfn_params.PUBLIC_ZONE_TITLE,
            template=root_stack.stack_template,
            Name=dns_params.DEFAULT_PUBLIC_DNS_ZONE,
            HostedZoneTags=Tags(CreatedByComposeX="True", PublicZone="True"),
            HostedZoneConfig=HostedZoneConfiguration(
                Comment=Sub("Public DNS Zone for ${AWS::StackName}")
            ),
        )
        if keyisset("Name", dns_settings[self.public_zone_key]):
            self.public_zone_name = dns_settings[self.public_zone_key]["Name"]

        elif keyisset("Lookup", dns_settings[self.public_zone_key]):
            self.set_public_zone_lookup_params(settings, dns_settings, root_stack)

        elif keyisset("Use", dns_settings[self.public_zone_key]):
            self.set_public_zone_use_params(settings, dns_settings)
        else:
            self.set_public_zone_default_params(settings, root_stack)
