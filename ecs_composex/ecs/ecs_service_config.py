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
Module for the ServiceConfig Class which is used for Container, Task and Service definitions.

"""
from troposphere import AWS_NO_VALUE
from troposphere import Ref
from troposphere.ecs import HealthCheck

from ecs_composex.common import NONALPHANUM
from ecs_composex.common import keyisset, LOG
from ecs_composex.common.config import ComposeXConfig
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.docker_tools import set_memory_to_mb


def keyset_else_novalue(key, obj, else_value=None):
    """
    Function to return value else set to Ref(NoValue)
    :param str key: key looked for in the dict
    :param dict obj: the dictionary to look into
    :param else_value: alternative value to set when not keyisset is False
    :return: value else Ref(AWS_NO_VALUE)
    """
    if not keyisset(key, obj):
        if else_value is None:
            return Ref(AWS_NO_VALUE)
        else:
            return else_value
    else:
        return obj[key]


def set_healthcheck(definition):
    """
    Function to set healtcheck configuration
    :return:
    """
    key = "healthcheck"
    valid_keys = ["test", "interval", "timeout", "retries", "start_period"]
    attr_mappings = {
        "test": "Command",
        "interval": "Interval",
        "timeout": "Timeout",
        "retries": "Retries",
        "start_period": "StartPeriod",
    }
    required_keys = ["test"]
    if not keyisset(key, definition):
        return None
    else:
        healthcheck = definition[key]
        for key in healthcheck.keys():
            if key not in valid_keys:
                raise AttributeError(f"Key {key} is not valid. Expected", valid_keys)
        if not all(required_keys) not in healthcheck.keys():
            raise AttributeError(
                f"Expected at least {required_keys}. Got", healthcheck.keys()
            )
        params = {}
        for key in healthcheck.keys():
            params[attr_mappings[key]] = healthcheck[key]
        if isinstance(params["Command"], str):
            params["Command"] = [healthcheck["test"]]
        if keyisset("Interval", params) and isinstance(params["Interval"], str):
            params["Interval"] = int(healthcheck["interval"])
        return HealthCheck(**params)


def define_protocol(port_string):
    """
    Function to define the port protocol. Defaults to TCP if not specified otherwise

    :param port_string: the port string to parse from the ports list in the compose file
    :type port_string: str
    :return: protocol, ie. udp or tcp
    :rtype: str
    """
    protocols = ["tcp", "udp"]
    protocol = "tcp"
    if port_string.find("/"):
        protocol_found = port_string.split("/")[-1].strip()
        if protocol_found in protocols:
            return protocol_found
    return protocol


def set_service_ports(ports):
    """Function to define common structure to ports

    :return: list of ports the ecs_service uses formatted according to dict
    :rtype: list
    """
    valid_keys = ["published", "target", "protocol", "mode"]
    service_ports = []
    for port in ports:
        if not isinstance(port, (str, dict, int)):
            raise TypeError(
                "ports must be of types", dict, "or", list, "got", type(port)
            )
        if isinstance(port, str):
            service_ports.append(
                {
                    "protocol": define_protocol(port),
                    "published": port.split(":")[0],
                    "target": port.split(":")[-1].split("/")[0].strip(),
                    "mode": "awsvpc",
                }
            )
        elif isinstance(port, dict):
            if not set(port).issubset(valid_keys):
                raise KeyError(f"Valid keys are", valid_keys, "got", port.keys())
            port["mode"] = "awsvpc"
            service_ports.append(port)
        elif isinstance(port, int):
            service_ports.append(
                {
                    "protocol": "tcp",
                    "published": port,
                    "target": port,
                    "mode": "awsvpc",
                }
            )
    LOG.debug(service_ports)
    return service_ports


class ServiceConfig(ComposeXConfig):
    """
    Class specifically dealing with the configuration and settings of the ecs_service from how it was defined in
    the compose file

    :cvar list keys: List of valid settings for a service in Docker compose syntax reference
    :cvar list service_config_keys: list of extra configuration that apply to services.
    :cvar bool use_cloudmap: Indicates whether or not the service will be added to the VPC CloudMap
    :cvar bool use_alb: Indicates to use an AWS Application LoadBalancer (ELBv2, type application)
    :cvar bool use_nlb: Indicates to use an AWS Application LoadBalancer (ELBv2, type network)
    :cvar bool is_public: Indicates whether the service should be accessible publicly
    :cvar str boundary: IAM boundary policy to use for the IAM Roles (Execution and Task)
    :cvar str lb_type: Indicates the type of ELBv2 to use (application or network)
    :cvar str hostname: the hostname to use to route to the service.
    :cvar str command: the command to use for the service start
    :cvar list ports: List of ports to use for the microservice.
    :cvar list links: list of links as indicated in the compose file, indicating connection dependencies.
    :cvar bool use_xray: Indicates whether or not add the X-Ray Daemon to the task definition.
    :cvar float cpu_alloc: CPU Allocated to the service
    :cvar float cpu_resa: CPU Reservation to the service
    :cvar int mem_alloc: Memory allocation for the service, in MB
    :cvar int mem_resa: Memory reserved to the service.
    """

    keys = [
        "image",
        "ports",
        "environment",
        "configs",
        "labels",
        "command",
        "hostname",
        "entrypoint",
        "volumes",
        "deploy",
        "external_links",
    ]
    service_config_keys = ["xray"]
    required_keys = ["image"]

    def __init__(self, content, service_name, definition, family_name=None):
        """
        Function to initialize the ecs_service configuration
        :param content:
        """
        service_configs = keyset_else_novalue(
            self.master_key, definition, else_value={}
        )
        for key in self.service_config_keys:
            if key not in self.valid_config_keys:
                self.valid_config_keys.append(key)
        super().__init__(content, service_name, service_configs)

        if not set(self.required_keys).issubset(set(definition)):
            raise AttributeError(
                "Required attributes for a ecs_service are", self.required_keys
            )
        self.family_dependents = []
        self.essential = False
        self.volumes = []
        self.links = (keyset_else_novalue("external_links", definition, else_value=[]),)
        self.service = None
        self.use_xray = False
        self.replicas = int(ecs_params.SERVICE_COUNT.Default)
        self.cpu_alloc = Ref(AWS_NO_VALUE)
        self.cpu_resa = Ref(AWS_NO_VALUE)
        self.mem_alloc = Ref(AWS_NO_VALUE)
        self.mem_resa = Ref(AWS_NO_VALUE)
        self.service_name = service_name
        self.resource_name = NONALPHANUM.sub("", service_name)
        self.command = (
            definition["command"].strip() if keyisset("command", definition) else None
        )
        self.entrypoint = keyset_else_novalue("entrypoint", definition, else_value=None)
        self.ports = (
            set_service_ports(definition["ports"])
            if keyisset("ports", definition)
            else []
        )
        self.environment = keyset_else_novalue("environment", definition, else_value=[])
        self.hostname = keyset_else_novalue("hostname", definition, else_value=None)
        self.family_name = family_name
        self.set_service_deploy(definition)
        self.lb_service_name = service_name
        self.set_xray(definition)
        self.healthcheck = set_healthcheck(definition)
        self.depends_on = keyset_else_novalue("depends_on", definition, else_value=[])

    def handle_add_with_dependency(self, other):
        """
        :param other:
        :return:
        """

    def __add__(self, other):
        """
        Function to merge two services config.
        """
        LOG.debug(f"Current LB: {self.lb_type}")
        if self.lb_type is None:
            if other.lb_type is not None:
                self.ports = other.ports
                self.lb_type = other.lb_type
                self.is_public = other.is_public

        elif self.lb_type is not None and other.lb_type is not None:
            if self.is_public:
                pass
            elif other.is_public and not self.is_public:
                self.ports = other.ports
                self.lb_type = other.lb_type
                self.lb_service_name = other.lb_service_name
                self.is_public = other.is_public
            elif not other.is_public and self.is_public:
                pass
        elif self.lb_type is not None and other.lb_type is None:
            pass
        LOG.debug(f"LB TYPE: {self.lb_type}")
        if other.use_xray or self.use_xray:
            self.use_xray = True
        if self.links or other.links:
            self.links += other.links
        return self

    def use_nlb(self):
        """
        Method to indicate if the current lb_type is network

        :return: True or False
        :rtype: bool
        """
        if self.lb_type == "network":
            return True
        return False

    def use_alb(self):
        """
        Method to indicate if the current lb_type is application

        :return: True or False
        :rtype: bool
        """
        if self.lb_type == "application":
            return True
        return False

    def set_compute_resources(self, resources):
        """
        Function to analyze the Docker Compose deploy attribute and set settings accordingly.
        deployment keys: replicas, mode, resources

        :param dict resources: Resources definition
        """
        if keyisset("limits", resources):
            if keyisset("cpus", resources["limits"]):
                self.cpu_alloc = int(float(resources["limits"]["cpus"]) * 1024)
            if keyisset("memory", resources["limits"]):
                self.mem_alloc = set_memory_to_mb(resources["limits"]["memory"].strip())
        if keyisset("reservations", resources):
            if keyisset("cpus", resources["reservations"]):
                self.cpu_resa = int(float(resources["reservations"]["cpus"]) * 1024)
            if keyisset("memory", resources["reservations"]):
                self.mem_resa = set_memory_to_mb(
                    resources["reservations"]["memory"].strip()
                )

    def set_deployment_settings(self, deployment):
        """
        Function to set the service deployment settings.
        """
        if keyisset("replicas", deployment):
            self.replicas = int(deployment["replicas"])

    def set_service_deploy(self, definition):
        """
        Function to setup the service configuration from the deploy section of the service in compose file.
        """
        if not keyisset("deploy", definition):
            return
        deployment = definition["deploy"]
        if keyisset("resources", deployment):
            self.set_compute_resources(deployment["resources"])
        self.set_deployment_settings(deployment)

    def set_xray(self, definition):
        """
        Function to set the xray
        """
        if keyisset(self.master_key, definition) and keyisset(
            "use_xray", definition[self.master_key]
        ):
            self.use_xray = True
