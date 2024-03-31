#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.compose.compose_services import ComposeService
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack
    from ecs_composex.ecs_ingress.ecs_ingress_stack import XStack as EcsIngressStack

from json import dumps

from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import AWS_ACCOUNT_ID, GetAtt, NoValue, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import (
    ServiceConnectClientAlias,
    ServiceConnectConfiguration,
    ServiceConnectService,
)

from ecs_composex.cloudmap.cloudmap_params import RES_KEY as CLOUDMAP_KEY
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters, add_resource
from ecs_composex.ecs.ecs_params import SERVICE_NAME
from ecs_composex.ingress_settings import Ingress
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import SG_ID_TYPE


def handle_ext_sources(existing_sources: list, new_sources: list) -> None:
    """
    Adds up external sources if they are not defined yet

    :param existing_sources:
    :param new_sources:
    """
    set_ipv4_sources = [
        s[Ingress.ipv4_key] for s in existing_sources if keyisset(Ingress.ipv4_key, s)
    ]
    for new_s in new_sources:
        if new_s[Ingress.ipv4_key] not in set_ipv4_sources:
            existing_sources.append(new_s)


def handle_aws_sources(existing_sources: list, new_sources: list) -> None:
    """
    Function to handle merge of aws sources between two services for one family
    :param existing_sources:
    :param new_sources:
    :return:
    """
    set_ids = [s["Id"] for s in existing_sources if keyisset("Id", s)]
    for new_s in new_sources:
        if keyisset("Id", new_s) and new_s["Id"] not in set_ids:
            existing_sources.append(new_s)


def handle_services(existing_sources: list, new_sources: list) -> None:
    """
    Function to merge source services definitions

    :param list existing_sources:
    :param list new_sources:
    :return:
    """
    set_ids = [s["Name"] for s in existing_sources if keyisset("Name", s)]
    for new_s in new_sources:
        if new_s["Name"] not in set_ids:
            existing_sources.append(new_s)


def handle_ingress_rules(source_config: dict, ingress_config: dict) -> None:
    valid_keys = [
        ("Myself", bool, None),
        (Ingress.ext_sources_key, list, handle_ext_sources),
        (Ingress.aws_sources_key, list, handle_aws_sources),
        (Ingress.services_key, list, handle_services),
    ]
    for key in valid_keys:
        if key[1] is bool:
            ingress_config[key[0]] = set_else_none(
                key[0], source_config, alt_value=False, eval_bool=True
            )
        elif keyisset(key[0], source_config) and key[2]:
            key[2](ingress_config[key[0]], source_config[key[0]])


def merge_family_network_setting(
    family, key: str, definition: dict, network: dict, network_config: dict
) -> None:
    """
    Merges a network setting (key) and its definition (definition) with new definition (network) into network_config

    If the key is x-cloudmap, and is unset, set to value. If another service of the family comes in, comes second.

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param str key:
    :param dict definition:
    :param dict network:
    :param dict network_config:
    :return:
    """
    if keyisset(key, network) and key == Ingress.master_key:
        handle_ingress_rules(network[key], network_config[key])
    elif keyisset(key, network) and key == CLOUDMAP_KEY:
        if definition:
            LOG.warning(
                family.name,
                f"x-network.{CLOUDMAP_KEY}",
                "is already set to",
                definition,
            )
        else:
            network_config[CLOUDMAP_KEY] = network[CLOUDMAP_KEY]


def merge_family_services_networking(family: ComposeFamily) -> dict:
    """
    Merge the different services network configuration definitions

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :return: The family network definition
    :rtype: dict
    """
    network_config = {
        Ingress.master_key: {
            "Myself": False,
            Ingress.ext_sources_key: [],
            Ingress.aws_sources_key: [],
            Ingress.services_key: [],
        },
        CLOUDMAP_KEY: {},
    }
    x_network_ingress = [s.x_network for s in family.ordered_services if s.x_network]
    for network in x_network_ingress:
        for key, definition in network_config.items():
            merge_family_network_setting(
                family, key, definition, network, network_config
            )
    LOG.debug(family.name)
    LOG.debug(dumps(network_config, indent=2))
    return network_config


def set_compose_services_ingress(
    dst_family: ComposeFamily,
    families_sg_stack: EcsIngressStack,
    settings: ComposeXSettings,
) -> None:
    """
    Function to crate SG Ingress between two families / services.
    Presently, the ingress rules are set after all services have been created
    """
    target_family_services: list[ComposeService] = []
    for _target_service_def in dst_family.service_networking.ingress.services:
        service_name = _target_service_def["Name"]
        for _service in settings.services:
            if service_name != _service.name:
                continue
            if _service.family == dst_family:
                continue
            target_family_services.append(_service)
    add_service_to_service_ingress_rules(
        dst_family, target_family_services, families_sg_stack
    )


def add_service_to_service_ingress_rules(
    dst_family: ComposeFamily,
    target_family_services: list[ComposeService],
    families_sg_stack: EcsIngressStack,
):
    """
    For each identified service that wants to access the `dst_family` services
    For each port of the `dst_family`
    Create an SG Ingress rule that allows service-to-service communication
    """
    for _service in target_family_services:
        if families_sg_stack.title not in _service.family.stack.DependsOn:
            _service.family.stack.DependsOn.append(families_sg_stack.title)
        for _service_port_def in dst_family.service_networking.ports:
            target_port = set_else_none(
                "target",
                _service_port_def,
                set_else_none("published", _service_port_def, None),
            )
            if target_port is None:
                raise ValueError(
                    "Wrong port definition value for security group ingress",
                    _service_port_def,
                )
            common_args = {
                "FromPort": target_port,
                "ToPort": target_port,
                "IpProtocol": _service_port_def["protocol"],
                "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
                "Description": Sub(
                    f"From ${_service.family.name} to {dst_family.name} "
                    f"on port {target_port}/{_service_port_def['protocol']}"
                ),
            }
            ingress_title: str = (
                f"From{_service.family.logical_name}To{dst_family.logical_name}"
                f"On{target_port}{_service_port_def['protocol'].title()}"
            )
            add_resource(
                families_sg_stack.stack_template,
                SecurityGroupIngress(
                    ingress_title,
                    SourceSecurityGroupId=GetAtt(
                        _service.family.service_networking.inter_services_sg.cfn_resource,
                        "GroupId",
                    ),
                    GroupId=GetAtt(
                        dst_family.service_networking.inter_services_sg.cfn_resource,
                        "GroupId",
                    ),
                    **common_args,
                ),
            )


def handle_str_cloudmap_config(
    family: ComposeFamily, family_mappings: dict, cloudmap_config: str, ports: list
) -> None:
    """
    Handle cloudmap config when config is set as str

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param dict family_mappings:
    :param str cloudmap_config:
    :param list ports:
    """
    if cloudmap_config not in family_mappings.keys():
        family_mappings[cloudmap_config] = {
            "Port": ports[0],
            "Name": family.family_hostname,
        }
    else:
        LOG.warning(
            f"{family.name}.x-network.x-cloudmap - {cloudmap_config} is set multiple times. "
            f"Preserving {family_mappings[cloudmap_config]}"
        )


def handle_dict_cloudmap_config(
    family: ComposeFamily, family_mappings: dict, cloudmap_config: dict, ports: list
) -> None:
    """
    Handles cloudmap config settings when set as a mapping/dict

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param dict family_mappings:
    :param dict cloudmap_config:
    :param list ports:
    """
    for map_name, config in cloudmap_config.items():
        if map_name in family_mappings.keys():
            LOG.warning(
                f"{family.name}.x-network.x-cloudmap - {cloudmap_config} is set multiple times. "
                f"Preserving {family_mappings[map_name]}"
            )
        else:
            if keyisset("Port", config):
                for port in ports:
                    if port["target"] == config["Port"]:
                        family_mappings[map_name] = {
                            "Port": port,
                            "Name": set_else_none(
                                "Name", config, family.family_hostname
                            ),
                        }
                        break
            else:
                family_mappings[map_name] = {
                    "Port": ports[0],
                    "Name": set_else_none("Name", config, family.family_hostname),
                }


def merge_cloudmap_settings(family: ComposeFamily, ports: list) -> dict:
    """
    Function to merge the x_cloudmap from the service

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param list[dict] ports:
    :return: The cloudmap config for the given family
    :rtype: dict
    """
    cloudmap_configs = [
        svc.x_cloudmap for svc in family.ordered_services if svc.x_cloudmap
    ]
    if not cloudmap_configs or not ports:
        return {}
    family_mappings = {}
    for cloudmap_config in cloudmap_configs:
        if isinstance(cloudmap_config, str):
            handle_str_cloudmap_config(family, family_mappings, cloudmap_config, ports)
        elif isinstance(cloudmap_config, dict):
            handle_dict_cloudmap_config(family, family_mappings, cloudmap_config, ports)
    return family_mappings


def find_namespace(
    family: ComposeFamily, namespace_id: str, settings: ComposeXSettings
):
    """Finds the x-cloudmap: namespace and returns the identifier to use for it"""
    x_resource_attribute: str = f"x-cloudmap::{namespace_id}::Arn"
    namespace, parameter = settings.get_resource_attribute(x_resource_attribute)
    return namespace.get_resource_attribute_value(parameter, family)[0]


def set_ecs_connect_from_macro(
    family: ComposeFamily,
    service: ComposeService,
    macro: dict,
    settings: ComposeXSettings,
) -> ServiceConnectConfiguration:
    """
    Based on the MacroParameters, creates the ServiceConnectConfiguration object.
    Configuration is in the `macro` parameter
    """
    LOG.info(f"{family.name}.{service.name} - Setting up ecs-connect settings")
    service_aliases: list[ServiceConnectService] = []
    props: dict = {
        "Enabled": True,
        "Namespace": find_namespace(family, macro["x-cloudmap"], settings),
        "Services": service_aliases,
    }
    if not keyisset("service_ports", macro):
        return ServiceConnectConfiguration(**props)

    for port_name, connect_config in macro["service_ports"].items():
        for the_port in family.service_networking.ports:
            if keyisset("name", the_port) and the_port["name"] == port_name:
                break
        else:
            raise AttributeError(
                f"No port called {port_name} in family {family.name}",
                [_port["name"] for _port in family.service_networking.ports],
            )

        dns_name = set_else_none("DnsName", connect_config, None)
        client_aliases = NoValue
        if dns_name:
            client_aliases = [
                ServiceConnectClientAlias(DnsName=dns_name, Port=the_port["target"])
            ]
        services_props: dict = {
            "DiscoveryName": set_else_none(
                "CloudMapServiceName", connect_config, family.name
            ),
            "PortName": port_name,
            "Timeout": set_else_none("Timeout", connect_config, NoValue),
            "IngressPortOverride": set_else_none(
                "IngressPortOverride", connect_config, NoValue
            ),
            "ClientAliases": client_aliases,
        }
        config: ServiceConnectService = ServiceConnectService(**services_props)
        service_aliases.append(config)

    return ServiceConnectConfiguration(**props)


def process_ecs_connect_settings(
    family: ComposeFamily, service: ComposeService, settings: ComposeXSettings
) -> ServiceConnectConfiguration | Ref:
    """Determines whether to create the ECS Service connect from the Properties or MacroParameters"""
    if keyisset("Properties", service.x_ecs_connect):
        props = import_record_properties(
            service.x_ecs_connect["Properties"], ServiceConnectConfiguration
        )
        connect_props = ServiceConnectConfiguration(**props)
    elif keyisset("MacroParameters", service.x_ecs_connect):
        connect_props = set_ecs_connect_from_macro(
            family, service, service.x_ecs_connect["MacroParameters"], settings
        )
    else:
        raise KeyError(
            f"{family.name} - x-network.x-ecs_connect is not set correctly. "
            "One of Properties or MacroParameters is required"
        )
    return connect_props


def import_set_ecs_connect_settings(
    family: ComposeFamily, settings: ComposeXSettings
) -> ServiceConnectConfiguration | None:
    if not family.service_networking.ports:
        LOG.warning(f"services.{family.name} - No ports defined: ignoring ECS Connect.")
        return
    x_ecs_configs: list[ComposeService] = [
        service for service in family.ordered_services if service.x_ecs_connect
    ]
    if not x_ecs_configs:
        return None
    if len(x_ecs_configs) > 1:
        raise ValueError(
            f"{family.name} - x-network.x-ecs_connect can only be set once for all the services of the family."
        )
    return process_ecs_connect_settings(family, x_ecs_configs[0], settings)
