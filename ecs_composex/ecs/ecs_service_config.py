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
from troposphere.iam import Policy

from ecs_composex.common import keyisset, keypresent, LOG
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.docker_tools import set_memory_to_mb
from ecs_composex.iam import define_iam_policy


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


def validate_healthcheck(healthcheck, valid_keys, required_keys):
    """
    Healthcheck definition validation

    :param dict healthcheck:
    :param list valid_keys:
    :param list required_keys:
    """
    for key in healthcheck.keys():
        if key not in valid_keys:
            raise AttributeError(f"Key {key} is not valid. Expected", valid_keys)
    if not all(required_keys) not in healthcheck.keys():
        raise AttributeError(
            f"Expected at least {required_keys}. Got", healthcheck.keys()
        )


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
    healthcheck = definition[key]
    validate_healthcheck(healthcheck, valid_keys, required_keys)
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
                    "published": int(port.split(":")[0]),
                    "target": int(port.split(":")[-1].split("/")[0].strip()),
                    "mode": "awsvpc",
                }
            )
        elif isinstance(port, dict):
            if not set(port).issubset(valid_keys):
                raise KeyError("Valid keys are", valid_keys, "got", port.keys())
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


def define_ingress_mappings(service_ports):
    """
    Function to create a mapping of sources for a common target
    """
    ingress_mappings = {}
    for port in service_ports:
        if port["target"] not in ingress_mappings.keys():
            ingress_mappings[port["target"]] = [port["published"]]
        elif (
            port["target"] in ingress_mappings.keys()
            and not port["published"] in ingress_mappings[port["target"]]
        ):
            ingress_mappings[port["target"]].append(port["published"])
    return ingress_mappings


class ServiceConfig(object):
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
    scaling_key = "scaling"
    required_keys = ["image"]

    master_key = "x-configs"
    composex_key = "composex"
    valid_config_keys = ["network", "iam", "x-ray", "logging", scaling_key]

    network_defaults = {
        "use_cloudmap": True,
        "is_public": False,
        "lb_type": None,
        "ingress": None,
    }

    def __init__(self, service, content, family_name=None):
        """
        Function to initialize the ecs_service configuration
        :param content:
        :param ecs_composex.common.compose_resources.XResource service:
        """
        self.resource = service
        service_configs = keyset_else_novalue(
            self.master_key, self.resource.definition, else_value={}
        )
        self.network = None
        self.iam = None
        self.lb_type = None
        self.healthcheck = None
        self.ext_sources = None
        self.aws_sources = None
        self.ingress_from_self = False
        self.is_public: False
        self.use_cloudmap = True
        self.use_appmesh = False
        self.boundary = None
        self.target_scaling_config = None
        self.scaling_range = None
        self.policies = []
        self.managed_policies = []
        self.container_start_condition = "START"
        self.replicas = int(ecs_params.SERVICE_COUNT.Default)
        self.family_dependents = []
        self.essential = False
        self.volumes = []
        self.cpu_alloc = Ref(AWS_NO_VALUE)
        self.cpu_resa = Ref(AWS_NO_VALUE)
        self.mem_alloc = Ref(AWS_NO_VALUE)
        self.mem_resa = Ref(AWS_NO_VALUE)
        self.service = None
        self.use_xray = False
        self.logs_retention_period = ecs_params.LOG_GROUP_RETENTION.Default
        if keyisset("x-appmesh", content):
            self.use_appmesh = True

        if keyisset(self.master_key, content):
            self.set_from_top_configs(content)
        if self.resource.name and isinstance(service_configs, dict):
            self.define_service_config(content, self.resource.name, service_configs)

        if not set(self.required_keys).issubset(set(self.resource.definition)):
            raise AttributeError(
                f"Service {self.resource.name} is missing required attributes."
                "Required attributes for a ecs_service are",
                self.required_keys,
            )

        self.links = keyset_else_novalue(
            "external_links", self.resource.definition, else_value=[]
        )
        self.command = (
            self.resource.definition["command"].strip()
            if keyisset("command", self.resource.definition)
            else None
        )
        self.entrypoint = keyset_else_novalue(
            "entrypoint", self.resource.definition, else_value=None
        )
        self.ports = (
            set_service_ports(self.resource.definition["ports"])
            if keyisset("ports", self.resource.definition)
            else []
        )
        self.ingress_mappings = define_ingress_mappings(self.ports)
        self.environment = keyset_else_novalue(
            "environment", self.resource.definition, else_value=[]
        )
        self.hostname = keyset_else_novalue(
            "hostname", self.resource.definition, else_value=None
        )
        self.family_name = family_name
        self.set_service_deploy(self.resource.definition)
        self.lb_service_name = self.family_name
        self.set_xray(self.resource.definition)
        self.healthcheck = set_healthcheck(self.resource.definition)
        self.depends_on = keyset_else_novalue(
            "depends_on", self.resource.definition, else_value=[]
        )

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
        LOG.debug(f"LB TYPE: {self.lb_type}")
        if other.use_xray or self.use_xray:
            self.use_xray = True
        if self.links or other.links:
            self.links += other.links
        if not self.target_scaling_config and other.target_scaling_config:
            self.target_scaling_config = other.target_scaling_config
        return self

    def add_managed_policies(self, policies):
        for policy in policies:
            policy_def = define_iam_policy(policy)
            self.managed_policies.append(policy_def)

    def set_target_scaling(self, config):
        """
        Method to define target_scaling

        :param dict config:
        :return:
        """
        allowed_keys = {
            "cpu_target": int,
            "memory_target": int,
            "lb_targets": int,
            "scale_in_cooldown": int,
            "scale_out_cooldown": int,
            "disable_scale_in": bool,
        }
        default_values = {
            "scale_out_cooldown": 300,
            "scale_in_cooldown": 300,
            "disable_scale_in": False,
        }
        scaling_configuration = {}
        for key in allowed_keys.keys():
            if not keyisset(key, config) and keypresent(key, default_values):
                scaling_configuration[key] = default_values[key]
            elif keypresent(key, config) and isinstance(config[key], allowed_keys[key]):
                scaling_configuration[key] = config[key]
            elif keyisset(key, config) and not isinstance(
                config[key], allowed_keys[key]
            ):
                raise TypeError(
                    f"Scaling configuration {key} is of type",
                    type(config[key]),
                    "Expected",
                    allowed_keys[key],
                )
        LOG.debug(scaling_configuration)
        self.target_scaling_config = scaling_configuration

    def init_scaling(self, config):
        """
        Method to setup target scaling for the service.
        :return:
        """
        LOG.debug("Setting target scaling")
        allowed_keys = {"range": str, "target_scaling": dict, "allow_zero": bool}
        if not all(key in list(allowed_keys.keys()) for key in config.keys()):
            raise KeyError(
                "Found invalid key. Got",
                config,
                "Allowed",
                allowed_keys,
            )
        if not keyisset("range", config):
            raise KeyError(
                "Missing range property. Range should written as follows: {min}-{max}"
            )
        self.scaling_range = {
            "max": int(config["range"].split("-")[-1]),
            "min": int(config["range"].split("-")[0]),
        }
        if keyisset("allow_zero", config) and not self.scaling_range["min"] == 0:
            self.scaling_range["min"] = 0
        if keyisset("target_scaling", config):
            self.set_target_scaling(config["target_scaling"])

    def add_policies(self, policies):

        for count, policy in enumerate(policies):
            name = (
                f"PolicyGenerated{count}"
                if not keyisset("name", policy)
                else policy["name"]
            )
            if not keyisset("document", policy):
                raise KeyError("You must set the policy document for the policy")
            if (
                keyisset("Version", policy["document"])
                and not isinstance(policy["document"]["Version"], str)
                or not keyisset("Version", policy["document"])
            ):
                policy["document"]["Version"] = "2012-10-17"
            policy_object = Policy(PolicyName=name, PolicyDocument=policy["document"])
            self.policies.append(policy_object)

    def init_iam(self, config):
        """
        Function to set IAM
        :return:
        """
        valid_keys = ["boundary", "managed_policies", "policies"]
        for key_name in config.keys():
            if key_name not in valid_keys:
                raise KeyError(
                    f"{key_name} is not a valid configuration for IAM. Accepted",
                    valid_keys,
                )
            if key_name == "boundary":
                setattr(self, key_name, config[key_name])
            elif key_name == "managed_policies" and isinstance(
                config["managed_policies"], list
            ):
                self.add_managed_policies(config["managed_policies"])
            elif key_name == "policies" and isinstance(config["policies"], list):
                self.add_policies(config["policies"])

    def init_logging(self, config):
        """
        Method to handle `logging`
        :param config:
        """
        allowed_keys = ["logs_retention_period"]
        for key in allowed_keys:
            if key not in allowed_keys:
                raise KeyError(
                    f"{key} not allowed setting for logging. Allowed", allowed_keys
                )
            if key in config and key == "logs_retention_period":
                setattr(
                    self,
                    key,
                    min(
                        ecs_params.LOG_GROUP_RETENTION.AllowedValues,
                        key=lambda x: abs(x - config[key]),
                    ),
                )

    def parse_ingress(self, ingress_settings):
        """
        Method to set the ingress_name for the service.
        :param ingress_settings:
        :return:
        """
        allowed_keys = ["ext_sources", "aws_sources", "myself"]
        for ingress_name in ingress_settings:
            if ingress_name not in allowed_keys:
                raise ValueError(
                    f"Setting {ingress_name} is not valid. Allowed", allowed_keys
                )
            if ingress_name == "myself" and ingress_settings["myself"]:
                self.ingress_from_self = True
            elif ingress_name == "ext_sources":
                self.ext_sources = ingress_settings[ingress_name]
            elif ingress_name == "aws_sources":
                self.aws_sources = ingress_settings[ingress_name]

    def init_network(self, config):
        """
        Function to define networking properties
        """
        for key_name in config.keys():
            if key_name not in self.network_defaults.keys():
                raise KeyError(
                    f"{key_name} is not a valid configuration for Networking"
                )
        for key_name in self.network_defaults:
            if key_name not in config.keys() and not hasattr(self, key_name):
                LOG.info(
                    f"Missing {key_name}. Setting to default - {self.resource.name}"
                )
                setattr(self, key_name, self.network_defaults[key_name])
            elif key_name in config.keys():
                LOG.debug(f"ELSE - {key_name}- {config[key_name]}")
                if key_name == "ingress":
                    self.parse_ingress(config[key_name])
                else:
                    setattr(self, key_name, config[key_name])

    def set_from_top_configs(self, compose_content):
        """
        Function to define the settings from global content
        :param compose_content:
        :return:
        """
        if keyisset(self.composex_key, compose_content[self.master_key]):
            for key in self.valid_config_keys:
                if keyisset(
                    key, compose_content[self.master_key][self.composex_key]
                ) and hasattr(self, f"init_{key}"):
                    init_function = getattr(self, f"init_{key}")
                    LOG.debug(init_function)
                    init_function(
                        compose_content[self.master_key][self.composex_key][key]
                    )

    def set_service_config(self, config):
        for key in self.valid_config_keys:
            if keyisset(key, config) and hasattr(self, f"init_{key}"):
                init_function = getattr(self, f"init_{key}")
                LOG.debug(init_function, config[key])
                init_function(config=config[key])

    def define_service_config(self, compose_content, service_name, config_definition):
        """
        Function to define the settings from global content
        :param config_definition:
        :param service_name:
        :param compose_content:
        :return:
        """
        if keyisset(self.master_key, compose_content) and keyisset(
            service_name, compose_content[self.master_key]
        ):
            LOG.debug(
                f"Service {service_name} has configuration in the root {self.master_key} section."
            )
            self.set_service_config(compose_content[self.master_key][service_name])
        self.set_service_config(config_definition)
        if self.use_appmesh and not self.use_cloudmap:
            LOG.warning(
                "You turned CloudMap off, however aim to use AppMesh. So we are enabling ClouMap for the services"
            )
            self.use_cloudmap = True

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
        depends_key = "ecs.depends.condition"
        deployment = definition["deploy"]
        if keyisset("resources", deployment):
            self.set_compute_resources(deployment["resources"])
        self.set_deployment_settings(deployment)
        if keyisset("labels", deployment) and keyisset(
            depends_key, deployment["labels"]
        ):
            allowed_values = ["START", "COMPLETE", "SUCCESS", "HEALTHY"]
            if deployment["labels"][depends_key] not in allowed_values:
                raise ValueError(
                    f"Attribute {depends_key} is invalid. Must be one of",
                    allowed_values,
                )
            self.container_start_condition = deployment["labels"][depends_key]

    def set_xray(self, definition):
        """
        Function to set the xray
        """
        if keyisset(self.master_key, definition) and keyisset(
            "use_xray", definition[self.master_key]
        ):
            self.use_xray = True
