#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere import AWS_NO_VALUE, GetAtt, Ref, Sub
from troposphere.ecs import ServiceRegistry
from troposphere.servicediscovery import DnsConfig, DnsRecord, HealthCheckCustomConfig
from troposphere.servicediscovery import Service as SdService

from ecs_composex.cloudmap.cloudmap_params import PRIVATE_NAMESPACE_ID
from ecs_composex.common import (
    add_parameters,
    add_resource,
    add_update_mapping,
    setup_logging,
)

LOG = setup_logging()


def create_registry(family, namespace, port_config, settings):
    """
    Creates the settings for the ECS Service Registries and adds the resources to the appropriate template

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param ecs_composex.cloudmap.cloudmap_stack.PrivateNamespace namespace:
    :param dict port_config:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if family.ecs_service.registries:
        LOG.warn(
            f"{family.name} already has a CloudMap mapping. "
            f"Only one can be set. Ignoring mapping to {namespace.name}"
        )
        return
    if namespace.cfn_resource:
        add_parameters(
            family.template,
            [namespace.attributes_outputs[PRIVATE_NAMESPACE_ID]["ImportParameter"]],
        )
        family.stack.Parameters.update(
            {
                namespace.attributes_outputs[PRIVATE_NAMESPACE_ID][
                    "ImportParameter"
                ].title: namespace.attributes_outputs[PRIVATE_NAMESPACE_ID][
                    "ImportValue"
                ]
            }
        )
        namespace_id = Ref(
            namespace.attributes_outputs[PRIVATE_NAMESPACE_ID]["ImportParameter"]
        )
    elif namespace.lookup_properties:
        add_update_mapping(
            family.template,
            namespace.mapping_key,
            settings.mappings[namespace.mapping_key],
        )
        namespace_id = namespace.attributes_outputs[PRIVATE_NAMESPACE_ID]["ImportValue"]
    else:
        raise AttributeError(
            f"{namespace.module_name}.{namespace.name} - Cannot define if new or lookup !?"
        )

    sd_service = SdService(
        f"{namespace.logical_name}EcsServiceDiscovery{family.logical_name}",
        Description=Sub(f"{family.name} service"),
        NamespaceId=namespace_id,
        HealthCheckCustomConfig=HealthCheckCustomConfig(FailureThreshold=1.0),
        DnsConfig=DnsConfig(
            RoutingPolicy="MULTIVALUE",
            NamespaceId=Ref(AWS_NO_VALUE),
            DnsRecords=[
                DnsRecord(TTL="15", Type="A"),
                DnsRecord(TTL="15", Type="SRV"),
            ],
        ),
        Name=family.family_hostname,
    )
    service_registry = ServiceRegistry(
        f"ServiceRegistry{port_config['target']}",
        RegistryArn=GetAtt(sd_service, "Arn"),
        Port=int(port_config["target"]),
    )
    add_resource(family.template, sd_service)
    family.ecs_service.registries.append(service_registry)


def map_namespace_to_service(namespaces, family, namespace_name, port_config, settings):
    """
    Function to map the x-cloudmap namespace to the service and create registries entries

    :param list[ecs_composex.cloudmap.cloudmap_stack.PrivateNamespace] namespaces:
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param str namespace_name:
    :param dict port_config:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """

    for _namespace in namespaces:
        if _namespace.name == namespace_name:
            LOG.info(
                f"{_namespace.module_name}.{_namespace} mapped to family service {family.name}"
            )
            create_registry(family, _namespace, port_config, settings)
            break


def cloudmap_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to link services to AWS CloudMap namespaces

    :param dict of {str: ecs_composex.cloudmap.cloudmap_stack.PrivateNamespace} resources:
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    new_resources = [res for res in resources.values() if res.cfn_resource]
    lookup_resources = [res for res in resources.values() if res.lookup_properties]
    for family in settings.families.values():
        if not family.ecs_service.network.cloudmap_config:
            continue
        for (
            namespace,
            port_config,
        ) in family.ecs_service.network.cloudmap_config.items():
            if namespace in [res.name for res in new_resources]:
                map_namespace_to_service(
                    new_resources, family, namespace, port_config, settings
                )
            elif namespace in [res.name for res in lookup_resources]:
                map_namespace_to_service(
                    lookup_resources, family, namespace, port_config, settings
                )
            else:
                raise LookupError(
                    "Failed to map",
                    family,
                    namespace,
                    "to any of",
                    [res.name for res in resources.values()],
                )
