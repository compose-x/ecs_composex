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
Module to handle creation of the DNS records for specific targets
"""

from copy import deepcopy
from re import compile

from troposphere import (
    AWS_STACK_NAME,
    AWS_REGION,
)
from troposphere import Ref, GetAtt
from troposphere.route53 import RecordSetType, AliasTarget, BaseRecordSet

from ecs_composex.common import NONALPHANUM, LOG
from ecs_composex.common import keyisset, add_outputs
from ecs_composex.common.ecs_composex import X_KEY
from ecs_composex.dns.dns_params import RES_KEY, PUBLIC_DNS_ZONE_ID
from ecs_composex.elbv2.elbv2_params import LB_DNS_ZONE_ID, LB_DNS_NAME
from ecs_composex.resources_import import import_record_properties


def define_external_record_set(properties):
    """
    Function to define a record set without any targets in ComposeX

    :param properties:
    :return:
    """
    props = import_record_properties(properties, BaseRecordSet)
    record = RecordSetType(
        f"ExternalR53Record{props['Type']}{NONALPHANUM.sub('', props['Name'])}"[:254],
        **props,
    )
    return record


def handle_elbv2_target(record, elbv2, settings, root_stack, dns_settings):
    """
    Function to define the TargetAlias properties for the record from an ELBv2

    :param Record record:
    :param ecs_composex.elbv2.elbv2_stack Elbv2 elbv2:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.dns.DnsSettings dns_settings:
    :return:
    """
    if elbv2.lookup and not elbv2.cfn_resource:
        LOG.error("Cannot associate Lookedup ELBv2 at this time.")
        return
    elbv2_root_stack = root_stack.stack_template.resources[record.target_mod]
    elbv2.init_outputs()
    elbv2.generate_outputs()
    add_outputs(elbv2_root_stack.stack_template, elbv2.outputs)
    alias_tgt = AliasTarget(
        HostedZoneId=GetAtt(
            elbv2_root_stack.title,
            f"Outputs.{elbv2.logical_name}{LB_DNS_ZONE_ID.title}",
        ),
        DNSName=GetAtt(
            elbv2_root_stack.title,
            f"Outputs.{elbv2.logical_name}{LB_DNS_NAME.title}",
        ),
    )
    record_props = import_record_properties(record.properties, BaseRecordSet)
    record_props["AliasTarget"] = alias_tgt
    record_props["Region"] = Ref(AWS_REGION)
    if (
        dns_settings.public_zone.id_value or dns_settings.public_zone.cfn_resource
    ) and not keyisset("HostedZoneId", record_props):
        record_props["HostedZoneId"] = dns_settings.public_zone.id_value
    elif (
        not dns_settings.public_zone
        or not dns_settings.public_zone.id_value
        or not dns_settings.public_zone.cfn_resource
        and not keyisset("HostedZoneId", record_props)
    ):
        raise ValueError(
            "No Public zone was defined, neither in x-dns or in the properties"
        )
    if not keyisset("SetIdentifier", record_props):
        record_props["SetIdentifier"] = Ref(AWS_STACK_NAME)
    record.cfn_resource = RecordSetType(
        f"Elv2R53Record{record_props['Type']}{NONALPHANUM.sub('', record_props['Name'])}"[
            :254
        ],
        **record_props,
    )
    root_stack.stack_template.add_resource(record.cfn_resource)


class Record(object):
    """
    Class to represent a DNS record
    """

    allowed_keys = [("Properties", dict), ("Target", str), ("Names", list)]
    alias_targets = [("elbv2", handle_elbv2_target), ("s3", None)]
    alias_target_types = [f"{X_KEY}{key[0]}" for key in alias_targets]

    def __init__(self, definition):
        self.definition = deepcopy(definition)
        self.target = None
        self.cfn_resource = None
        for prop in self.definition.keys():
            if prop not in [key[0] for key in self.allowed_keys]:
                raise KeyError(
                    f"Property {prop} is not valid. Only properties are",
                    [key[0] for key in self.allowed_keys],
                )
        for key in self.allowed_keys:
            if keyisset(key[0], self.definition) and not isinstance(
                self.definition[key[0]], key[1]
            ):
                raise TypeError(
                    f"Property {key[0]} must be of type",
                    key[1],
                    "Got",
                    type(self.definition[key[0]]),
                )
        if keyisset("Target", self.definition):
            target_definition = self.definition["Target"].split("::")
            if not target_definition[0] in self.alias_target_types:
                raise ValueError(
                    f"ComposeX resource type {target_definition[0]} is not valid. It must be one of",
                    self.alias_target_types,
                )
            self.target_type = target_definition[0]
            self.target_name = target_definition[1]
            self.target_mod = compile(X_KEY).sub("", self.target_type)
        else:
            self.target_type = None
            self.target_name = None
        self.properties = (
            self.definition["Properties"]
            if keyisset("Properties", self.definition)
            else {}
        )
        self.names = (
            self.definition["Names"] if keyisset("Names", self.definition) else {}
        )
        self.validate_names()

    def validate_names(self):
        domain_name_re = compile(
            r"(?:(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9])$"
        )
        if self.names:
            for name in self.names:
                if not isinstance(name, str):
                    raise TypeError(
                        "the Names in the records definition must be a list of strings. Got",
                        type(name),
                    )
                if not domain_name_re.match(name):
                    raise NameError(
                        "The value",
                        name,
                        "is invalid. domain name must comply with",
                        domain_name_re.pattern,
                    )

    def map_record_to_target(self, settings, root_stack, dns_settings):
        """
        Method to go and identify the target resource

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ecs_composex.common.stacks.ComposeXStack root_stack:
        :param ecs_composex.dns.DnsSettings dns_settings:
        :return:
        """
        if keyisset(self.target_type, settings.compose_content) and keyisset(
            self.target_name, settings.compose_content[self.target_type]
        ):
            target = settings.compose_content[self.target_type][self.target_name]
            for target_type in self.alias_targets:
                if target_type[0] == self.target_mod and target_type[1]:
                    target_type[1](self, target, settings, root_stack, dns_settings)
                    break


class DnsRecords(object):

    main_key = "Records"

    def __init__(self, settings):
        """
        Function to update the DNS Records in compose content with the class

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        self.records = []
        if keyisset(RES_KEY, settings.compose_content) and keyisset(
            self.main_key, settings.compose_content[RES_KEY]
        ):
            for record in settings.compose_content[RES_KEY][self.main_key]:
                dns_record = Record(record)
                self.records.append(dns_record)

    def associate_records_to_resources(self, settings, root_stack, dns_settings):
        for dns_record in self.records:
            if dns_record.target_name and dns_record.target_type:
                dns_record.map_record_to_target(settings, root_stack, dns_settings)
