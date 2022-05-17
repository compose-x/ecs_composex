#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

import ecs_composex.common.troposphere_tools

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.common.stacks import ComposeXStack

from json import dumps

from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import AWS_ACCOUNT_ID, GetAtt, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.cloudmap.cloudmap_params import RES_KEY as CLOUDMAP_KEY
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters
from ecs_composex.ecs.ecs_params import SERVICE_NAME_T
from ecs_composex.ingress_settings import Ingress
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


def add_independent_rules(
    dst_family: ComposeFamily, service_name: str, root_stack: ComposeXStack
) -> None:
    """
    Adds security groups rules in the root stack as both services need to be created (with their SG)
    before the ingress rule can be defined.

    :param dst_family:
    :param service_name:
    :param root_stack:
    :return:
    """
    src_service_stack = root_stack.stack_template.resources[service_name]
    for port in dst_family.service_networking.ports:
        target_port = set_else_none(
            "published", port, alt_value=set_else_none("target", port, None)
        )
        if target_port is None:
            raise ValueError(
                "Wrong port definition value for security group ingress", port
            )
        ingress_rule = SecurityGroupIngress(
            f"From{src_service_stack.title}To{dst_family.logical_name}On{target_port}",
            FromPort=target_port,
            ToPort=target_port,
            IpProtocol=port["protocol"],
            Description=Sub(
                f"From {src_service_stack.title} to {dst_family.logical_name}"
                f" on port {target_port}/{port['protocol']}"
            ),
            GroupId=GetAtt(
                dst_family.stack.title,
                f"Outputs.{dst_family.logical_name}GroupId",
            ),
            SourceSecurityGroupId=GetAtt(
                src_service_stack.title,
                f"Outputs.{src_service_stack.title}GroupId",
            ),
            SourceSecurityGroupOwnerId=Ref(AWS_ACCOUNT_ID),
        )
        if ingress_rule.title not in root_stack.stack_template.resources:
            root_stack.stack_template.add_resource(ingress_rule)


def add_dependant_ingress_rules(
    dst_family: ComposeFamily, dst_family_sg_param: Parameter, src_family: ComposeFamily
) -> None:
    for port in dst_family.service_networking.ports:
        target_port = set_else_none(
            "published", port, alt_value=set_else_none("target", port, None)
        )
        if target_port is None:
            raise ValueError(
                "Wrong port definition value for security group ingress", port
            )
        common_args = {
            "FromPort": target_port,
            "ToPort": target_port,
            "IpProtocol": port["protocol"],
            "SourceSecurityGroupOwnerId": Ref(AWS_ACCOUNT_ID),
            "Description": Sub(
                f"From ${{{SERVICE_NAME_T}}} to {dst_family.stack.title} on port {target_port}"
            ),
        }
        src_family.template.add_resource(
            SecurityGroupIngress(
                f"From{src_family.logical_name}To{dst_family.stack.title}On{target_port}",
                SourceSecurityGroupId=GetAtt(
                    src_family.service_networking.security_group, "GroupId"
                ),
                GroupId=Ref(dst_family_sg_param),
                **common_args,
            )
        )


def set_compose_services_ingress(
    root_stack, dst_family: ComposeFamily, families: list, settings: ComposeXSettings
) -> None:
    """
    Function to crate SG Ingress between two families / services.
    Presently, the ingress rules are set after all services have been created

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.ecs.ecs_family.ComposeFamily dst_family:
    :param list families: The list of family names.
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for service in dst_family.service_networking.ingress.services:
        service_name = service["Name"]
        if service_name not in families:
            raise KeyError(
                f"The service {service_name} is not among the services created together. Valid services are",
                families,
            )
        if not keypresent("DependsOn", service):
            add_independent_rules(dst_family, service_name, root_stack)
        else:
            src_family = settings.families[service_name]
            if dst_family.stack.title not in src_family.stack.DependsOn:
                src_family.stack.DependsOn.append(dst_family.stack.title)
            dst_family_sg_param = Parameter(
                f"{dst_family.stack.title}GroupId", Type=SG_ID_TYPE
            )
            add_parameters(src_family.template, [dst_family_sg_param])
            src_family.stack.Parameters.update(
                {
                    dst_family_sg_param.title: GetAtt(
                        dst_family.stack.title,
                        f"Outputs.{dst_family.logical_name}GroupId",
                    ),
                }
            )
            add_dependant_ingress_rules(dst_family, dst_family_sg_param, src_family)


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
        family_mappings[cloudmap_config] = ports[0]
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
                        family_mappings[map_name] = port
                        break
            else:
                family_mappings[map_name] = ports[0]


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
