#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Manage the registration of x-resources into AWS CloudMap namespace
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.compose.x_resources.network_x_resources import (
        NetworkXResource,
        DatabaseXResource,
    )
    from ecs_composex.cloudmap.cloudmap_stack import PrivateNamespace

from compose_x_common.compose_x_common import keyisset
from troposphere import NoValue, Ref
from troposphere.servicediscovery import DnsConfig, DnsRecord, Instance, Service

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_parameters,
    add_resource,
    add_update_mapping,
)

from .cloudmap_params import PRIVATE_NAMESPACE_ID


def process_dns_config(
    namespace: PrivateNamespace,
    resource: NetworkXResource | DatabaseXResource,
    dns_settings: dict,
    settings: ComposeXSettings,
    service: Service,
    instance: Instance,
) -> None:
    """
    Process the DnsSettings of the x-cloudmap configuration
    """
    hostname = (
        dns_settings["Hostname"]
        if keyisset("Hostname", dns_settings)
        else resource.logical_name
    )
    if namespace.zone_name not in hostname:
        hostname = f"{hostname}.{namespace.zone_name}"
    record = DnsRecord(Type="CNAME", TTL="15")
    config = DnsConfig(DnsRecords=[record], NamespaceId=NoValue)
    setattr(service, "DnsConfig", config)
    setattr(service, "Name", hostname)

    if not hasattr(resource, "db_cluster_endpoint_param"):
        return

    attribute_pointer = resource.attributes_outputs[resource.db_cluster_endpoint_param]
    if resource.cfn_resource:
        add_parameters(
            namespace.stack.stack_template, [attribute_pointer["ImportParameter"]]
        )
        namespace.stack.Parameters.update(
            {
                attribute_pointer["ImportParameter"].title: attribute_pointer[
                    "ImportValue"
                ]
            }
        )
        instance.InstanceAttributes.update(
            {"AWS_INSTANCE_CNAME": Ref(attribute_pointer["ImportParameter"])}
        )
    else:
        add_update_mapping(
            namespace.stack.stack_template,
            resource.module.mapping_key,
            settings.mappings[resource.module.mapping_key],
        )
        instance.InstanceAttributes.update(
            {"AWS_INSTANCE_CNAME": attribute_pointer["ImportValue"]}
        )


def process_return_values(
    namespace: PrivateNamespace,
    resource,
    return_values: dict,
    instance_props: dict,
    settings,
):
    """
    Processes the ReturnValues attributes to assign to an instance.

    :param namespace:
    :param ecs_composex.compose.x_resources.XResource resource:
    :param dict return_values:
    :param dict instance_props:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for key, value in return_values.items():
        for attribute_param in resource.attributes_outputs.keys():
            if attribute_param.title == key or (
                attribute_param.return_value and attribute_param.return_value == key
            ):
                break
        else:
            raise KeyError(
                f"{resource.module.res_key}.{resource.name}"
                " - ReturnValue {key} not found. Available",
                [p.title for p in resource.attributes_outputs.keys()],
            )
        attribute_pointer = resource.attributes_outputs[attribute_param]
        if resource.cfn_resource:
            add_parameters(
                namespace.stack.stack_template, [attribute_pointer["ImportParameter"]]
            )
            namespace.stack.Parameters.update(
                {
                    attribute_pointer["ImportParameter"].title: attribute_pointer[
                        "ImportValue"
                    ]
                }
            )
            instance_props["InstanceAttributes"][key] = Ref(
                attribute_pointer["ImportParameter"]
            )
        else:
            add_update_mapping(
                namespace.stack.stack_template,
                resource.module.mapping_key,
                settings.mappings[resource.module.mapping_key],
            )
            instance_props["InstanceAttributes"][value] = attribute_pointer[
                "ImportValue"
            ]


def process_additional_attributes(additional_attributes: dict, instance_props: dict):
    """
    Processes the ReturnValues attributes to assign to an instance.

    :param dict additional_attributes:
    :param dict instance_props:
    """
    for key, value in additional_attributes.items():
        if key.startswith("AWS_"):
            continue
        instance_props["InstanceAttributes"][key] = value


def handle_resource_cloudmap_settings(
    namespace: PrivateNamespace, resource, cloudmap_settings: dict, settings
) -> None:
    """
    Function to handle x-cloudmap.{} settings

    :type namespace: class`ecs_composex.cloudmap.cloudmap_stack.PrivateNamespace`
    :type resource: class`Union[DatabaseXResource, NetworkXResource]`
    :type settings: class`ecs_composex.common.settings.ComposeXSettings`
    """
    if cloudmap_settings["Namespace"] != namespace.name:
        LOG.debug("NAMESPACE DOES NOT MATCH", cloudmap_settings, namespace.name)
        return
    if not resource.cfn_resource and not keyisset("ForceRegister", cloudmap_settings):
        LOG.debug("LOOKUP AND NO FORCE", cloudmap_settings)
        return
    resource_service_title = (
        f"{resource.module.mapping_key}{resource.logical_name}Service"
    )
    if resource_service_title in namespace.stack.stack_template.resources:
        LOG.debug("ALREADY BEEN PROCESSED", resource.name)
        return
    LOG.debug(
        "PROCESSING IN HANDLER",
        resource.module.res_key,
        resource.name,
        cloudmap_settings,
    )
    namespace_id_pointer = (
        namespace.attributes_outputs[PRIVATE_NAMESPACE_ID]["ImportValue"]
        if not namespace.cfn_resource
        else Ref(namespace.cfn_resource)
    )
    service_props = {
        "Description": f"{resource.name}",
        "NamespaceId": namespace_id_pointer,
        "Type": "HTTP",
    }
    instance_props = {"InstanceAttributes": {}}
    if keyisset("ReturnValues", cloudmap_settings):
        process_return_values(
            namespace,
            resource,
            cloudmap_settings["ReturnValues"],
            instance_props,
            settings,
        )
    if keyisset("AdditionalAttributes", cloudmap_settings):
        process_additional_attributes(
            cloudmap_settings["AdditionalAttributes"], instance_props
        )
    resource_service = Service(resource_service_title, **service_props)

    instance_props["ServiceId"] = Ref(resource_service)
    resource_instance = Instance(f"{resource_service_title}Instance", **instance_props)

    if keyisset("DnsSettings", cloudmap_settings) and resource.cloudmap_dns_supported:
        del service_props["Type"]
        process_dns_config(
            namespace,
            resource,
            cloudmap_settings["DnsSettings"],
            settings,
            resource_service,
            resource_instance,
        )
    elif not resource.cloudmap_dns_supported and keyisset(
        "DnsSettings", cloudmap_settings
    ):
        LOG.warning(
            f"{resource.module.res_key}.{resource.name}"
            " does not support DnsSettings for x-cloudmap."
        )
    add_resource(namespace.stack.stack_template, resource_service)
    add_resource(namespace.stack.stack_template, resource_instance)
