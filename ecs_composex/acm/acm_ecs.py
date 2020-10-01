#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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
Module to map services LBs settings to ACM certificate settings.
"""

from troposphere.elasticloadbalancingv2 import (
    Listener,
    Certificate,
)

from ecs_composex.acm import acm_params
from ecs_composex.common import LOG, keyisset
from ecs_composex.common.outputs import get_import_value
from ecs_composex.ecs.ecs_template import get_service_family_name


def find_service_listener(port_number, service_template):
    """
    Function to find the listener based on the port.

    :param int port_number: the port number of the listener
    :param troposphere.Template service_template: the service template
    :return: listener
    :rtype: troposphere.loadbalancingv2.Listener
    """
    for resource_name in service_template.resources:
        resource = service_template.resources[resource_name]
        if isinstance(resource, Listener) and resource.Port == port_number:
            return resource


def add_ssl_config_to_listeners(service_template, cert_import, ports):
    """
    Function to add the SSL settings to the listener of the LB

    :param service_template:
    :param cert_import:
    :param list ports: list of ports (int)
    :return:
    """
    for port in ports:
        if not isinstance(port, int):
            raise TypeError("Port must be of type", int, "got", type(port))
        listener = find_service_listener(port, service_template)
        if listener.Protocol == "HTTP":
            listener.Protocol = "HTTPS"
            setattr(
                listener,
                "Certificates",
                [Certificate(CertificateArn=cert_import)],
            )
        elif listener.Protocol == "TCP":
            listener.Protocol = "TLS"


def apply_to_ecs(
    cert_import, cert_def, services_families, services_stack, acm_root_stack
):
    for service in cert_def["Services"]:
        service_family = get_service_family_name(services_families, service["name"])
        if service_family not in services_stack.stack_template.resources:
            raise AttributeError(
                f"No service {service_family} present in services stack"
            )
        if not keyisset("ports", service):
            raise AttributeError(f"Missing ports for service {service_family}")
        service_stack = services_stack.stack_template.resources[service_family]
        service_template = service_stack.stack_template
        add_ssl_config_to_listeners(service_template, cert_import, service["ports"])
        if acm_root_stack.title not in services_stack.DependsOn:
            services_stack.DependsOn.append(acm_root_stack.title)


def acm_to_ecs(acms, services_stack, services_families, acm_root_stack, settings):
    """
    Function to apply ACM settings to ECS Services

    :param acms:
    :param services_stack:
    :param services_families:
    :param acm_root_stack:
    """
    for cert_name in acms:
        cert_def = acms[cert_name]
        if cert_name not in acm_root_stack.stack_template.resources:
            raise KeyError(f"DB {cert_name} not defined in RDS Root template")
        if not keyisset("Services", cert_def):
            LOG.warn(f"DB {cert_name} has no services defined.")
            continue
        cert_import = get_import_value(cert_name, acm_params.CERT_CN_T)
        apply_to_ecs(
            cert_import, cert_def, services_families, services_stack, acm_root_stack
        )
