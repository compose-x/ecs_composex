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

import re
from json import dumps
from copy import deepcopy

from troposphere import Parameter, Tags
from troposphere import Sub, Ref, GetAtt, ImportValue
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_REGION,
    AWS_STACK_NAME,
    AWS_PARTITION,
)
from troposphere.ecs import (
    HealthCheck,
    Environment,
    PortMapping,
    LogConfiguration,
    ContainerDefinition,
    TaskDefinition,
)
from troposphere.iam import Policy

from ecs_composex.common import keyisset, keypresent
from ecs_composex.common import NONALPHANUM, LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common.compose_secrets import (
    ComposeSecret,
    match_secrets_services_config,
)
from ecs_composex.common.compose_volumes import (
    ComposeVolume,
    handle_volume_dict_config,
    handle_volume_str_config,
)

from ecs_composex.ecs.ecs_params import LOG_GROUP, AWS_XRAY_IMAGE
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs import ecs_params, ecs_conditions
from ecs_composex.ecs.docker_tools import find_closest_fargate_configuration
from ecs_composex.ecs.ecs_conditions import USE_HOSTNAME_CON_T
from ecs_composex.ecs.ecs_iam import add_service_roles, expand_role_polices
from ecs_composex.ecs.ecs_params import NETWORK_MODE, EXEC_ROLE_T, TASK_ROLE_T, TASK_T
from ecs_composex.ecs.ecs_params import SERVICE_NAME, SERVICE_HOSTNAME
from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION
from ecs_composex.ecs.ecs_service_network_config import set_service_ports

NUMBERS_REG = r"[^0-9.]"
MINIMUM_SUPPORTED = 4


def import_secrets(template, service, container, settings):
    """
    Function to import secrets from composex mapping to AWS Secrets in Secrets Manager

    :param troposphere.Template template:
    :param troposhere.ecs.ContainerDefinition container:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if not service.secrets:
        return
    if not keyisset("secrets", settings.compose_content):
        return
    else:
        settings_secrets = settings.compose_content["secrets"]
    for secret in service.secrets:
        if (
            isinstance(secret, str)
            and secret in settings_secrets
            and keyisset("ComposeSecret", settings_secrets[secret])
        ):
            settings_secrets[secret]["ComposeSecret"].assign_to_task_definition(
                template, container
            )
        elif isinstance(secret, dict) and keyisset("source", secret):
            secret_name = secret["source"]
            if keyisset("ComposeSecret", settings_secrets[secret_name]):
                settings_secrets[secret_name][
                    "ComposeSecret"
                ].assign_to_task_definition(template, container)


def define_string_interpolation(var_value):
    """
    Function to determine whether an env variable string should use Sub.

    :param str var_value: The env var string as defined in compose file
    :return: String as is or Sub for interpolation
    :rtype: str
    """
    if var_value.find(r"${AWS::") >= 0:
        LOG.debug(var_value)
        return Sub(var_value)
    return var_value


def import_env_variables(environment):
    """
    Function to import Docker compose env variables into ECS Env Variables

    :param environment: Environment variables as defined on the ecs_service definition
    :type environment: dict
    :return: list of Environment
    :rtype: list<troposphere.ecs.Environment>
    """
    env_vars = []
    for key in environment:
        if not isinstance(environment[key], str):
            env_vars.append(Environment(Name=key, Value=str(environment[key])))
        else:
            env_vars.append(
                Environment(
                    Name=key, Value=define_string_interpolation(environment[key])
                )
            )
    return env_vars


def extend_container_secrets(container, secret):
    """
    Function to add secrets to a Container definition

    :param container: container definition
    :type container: troposphere.ecs.ContainerDefinition
    :param secret: secret to add
    :type secret: troposphere.ecs.Secret
    """
    if hasattr(container, "Secrets"):
        secrets = getattr(container, "Secrets")
        if secrets:
            uniq = [secret.Name for secret in secrets]
            if secret.Name not in uniq:
                secrets.append(secret)
        else:
            setattr(container, "Secrets", [secret])
    else:
        setattr(container, "Secrets", [secret])


def extend_container_envvars(container, env_vars):
    ignored_containers = ["xray-daemon", "envoy"]
    if (
        isinstance(container, ContainerDefinition)
        and not isinstance(container.Name, (Ref, Sub, GetAtt, ImportValue))
        and container.Name in ignored_containers
    ):
        LOG.debug(f"Ignoring AWS Container {container.Name}")
        return
    environment = (
        getattr(container, "Environment")
        if hasattr(container, "Environment")
        and not isinstance(getattr(container, "Environment"), Ref)
        else []
    )
    if environment:
        existing = [var.Name for var in environment]
        for var in env_vars:
            if var.Name not in existing:
                LOG.debug(f"Adding {var.Name} to {existing}")
                environment.append(var)

    else:
        setattr(container, "Environment", env_vars)
    LOG.debug(f"{container.Name}, {[env.Name for env in environment]}")


def handle_bytes(value):
    """
    Function to handle the KB use-case

    :param value: the string value
    :rtype: int or Ref(AWS_NO_VALUE)
    """
    amount = float(re.sub(NUMBERS_REG, "", value))
    unit = "Bytes"
    if amount < (MINIMUM_SUPPORTED * 1024 * 1024):
        LOG.warn(
            f"You set unit to {unit} and value is lower than 4MB. Setting to minimum supported by Docker"
        )
        return MINIMUM_SUPPORTED
    else:
        final_amount = (amount / 1024) / 1024
    return final_amount


def handle_kbytes(value):
    """
    Function to handle KB use-case
    """
    amount = float(re.sub(NUMBERS_REG, "", value))
    unit = "KBytes"
    if amount < (MINIMUM_SUPPORTED * 1024):
        LOG.warn(
            f"You set unit to {unit} and value is lower than 512MB. Setting to minimum supported by Docker"
        )
        return MINIMUM_SUPPORTED
    else:
        final_amount = int(amount / 1024)
    return final_amount


def set_memory_to_mb(value):
    """
    Returns the value of MB. If no unit set, assuming MB
    :param value: the string value
    :rtype: int or Ref(AWS_NO_VALUE)
    """
    b_pat = re.compile(r"(^[0-9.]+(b|B)$)")
    kb_pat = re.compile(r"(^[0-9.]+(k|kb|kB|Kb|K|KB)$)")
    mb_pat = re.compile(r"(^[0-9.]+(m|mb|mB|Mb|M|MB)$)")
    gb_pat = re.compile(r"(^[0-9.]+(g|gb|gB|Gb|G|GB)$)")
    amount = float(re.sub(NUMBERS_REG, "", value))
    unit = "MBytes"
    if b_pat.findall(value):
        final_amount = handle_bytes(value)
    elif kb_pat.findall(value):
        final_amount = handle_kbytes(value)
    elif mb_pat.findall(value):
        final_amount = int(amount)
    elif gb_pat.findall(value):
        unit = "GBytes"
        final_amount = int(amount) * 1024
    else:
        raise ValueError(f"Could not parse {value} to units")
    LOG.debug(f"Computed unit for {value}: {unit}. Results into {final_amount}MB")
    return final_amount


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


class ComposeService(object):
    """
    Class to represent a service

    :cvar str container_name: name of the container to use in definitions
    """

    main_key = "services"
    keys = [
        ("image", str),
        ("ports", list),
        ("environment", dict),
        ("configs", dict),
        ("labels", dict),
        ("command", str),
        ("hostname", str),
        ("entrypoint", str),
        ("volumes", list),
        ("deploy", dict),
        ("external_links", list),
        ("depends_on", list),
        ("links", list),
        ("secrets", list),
        ("healthcheck", dict),
        ("x-configs", dict),
    ]

    def __init__(self, name, definition, volumes=None, secrets=None):
        if not isinstance(definition, dict):
            raise TypeError(
                "The definition of a service must be", dict, "got", type(definition)
            )
        if not all(
            key in [title[0] for title in self.keys] for key in definition.keys()
        ):
            raise KeyError(
                "Only valid keys for a service definition are",
                self.keys[0],
                "Got",
                definition.keys(),
            )
        for setting in self.keys:
            if keyisset(setting[0], definition) and not isinstance(
                definition[setting[0]], setting[1]
            ):
                raise TypeError(
                    setting[0],
                    "is of type",
                    type(definition[setting][0]),
                    "Expected",
                    setting[1],
                )
        self.name = name
        self.x_configs = (
            definition["x-configs"] if keyisset("x-configs", definition) else None
        )
        self.replicas = 1
        self.container = None
        self.volumes = []
        self.secrets = []
        self.environment = (
            definition["environment"] if keyisset("environment", definition) else None
        )
        self.cfn_environment = (
            import_env_variables(self.environment)
            if self.environment
            else Ref(AWS_NO_VALUE)
        )
        self.ports = (
            set_service_ports(definition["ports"])
            if keyisset("ports", definition)
            else []
        )
        self.depends_on = (
            definition["depends_on"] if keyisset("depends_on", definition) else []
        )
        self.definition = definition
        self.command = (
            definition["command"].strip().split(";")
            if keyisset("command", definition)
            else Ref(AWS_NO_VALUE)
        )
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.container_name = name
        self.service_name = Sub(f"${{{ROOT_STACK_NAME.title}}}-{self.name}")
        self.image = self.definition["image"]
        self.image_param = Parameter(
            f"{self.logical_name}ImageUrl", Default=self.image, Type="String"
        )
        self.deploy = (
            self.definition["deploy"] if keyisset("deploy", self.definition) else None
        )
        self.ingress_mappings = define_ingress_mappings(self.ports)
        self.mem_alloc = None
        self.mem_resa = None
        self.cpu_amount = None
        self.families = []
        self.container_definition = None

        self.container_start_condition = "START"
        self.healthcheck = (
            definition["healthcheck"] if keyisset("healthcheck", definition) else None
        )
        self.ecs_healthcheck = Ref(AWS_NO_VALUE)
        self.set_ecs_healthcheck()
        self.container_parameters = {}

        self.map_volumes(volumes)
        self.map_secrets(secrets)
        self.set_service_deploy()
        self.set_container_definition()

    def set_container_definition(self):
        self.container_definition = ContainerDefinition(
            Image=Ref(self.image_param),
            Name=self.name,
            Cpu=self.cpu_amount if self.cpu_amount else Ref(AWS_NO_VALUE),
            Memory=self.mem_alloc if self.mem_alloc else Ref(AWS_NO_VALUE),
            MemoryReservation=self.mem_resa if self.mem_resa else Ref(AWS_NO_VALUE),
            PortMappings=[
                PortMapping(ContainerPort=port, HostPort=port)
                for port in self.ingress_mappings.keys()
            ]
            if self.ports
            else Ref(AWS_NO_VALUE),
            Environment=self.cfn_environment,
            LogConfiguration=LogConfiguration(
                LogDriver="awslogs",
                Options={
                    "awslogs-group": Ref(LOG_GROUP),
                    "awslogs-region": Ref(AWS_REGION),
                    "awslogs-stream-prefix": self.name,
                },
            ),
            Command=self.command,
            HealthCheck=self.ecs_healthcheck,
            DependsOn=Ref(AWS_NO_VALUE),
            Essential=True,
            Secrets=[secret.ecs_secret for secret in self.secrets],
        )
        self.container_parameters.update({self.image_param.title: self.image})

    def map_volumes(self, volumes=None):
        """
        Method to apply mapping of volumes to the service and define the mapping configuration

        :param list volumes:
        :return:
        """
        if keyisset(ComposeVolume.main_key, self.definition) and volumes:
            for s_volume in self.definition[ComposeVolume.main_key]:
                volume_config = None
                if isinstance(s_volume, str):
                    handle_volume_str_config(self, s_volume, volumes)
                elif isinstance(s_volume, dict):
                    handle_volume_dict_config(self, s_volume, volumes)
                self.volumes.append(volume_config)

    def map_secrets(self, secrets):
        if keyisset(ComposeSecret.main_key, self.definition) and secrets:
            for s_secret in self.definition[ComposeSecret.main_key]:
                match_secrets_services_config(self, s_secret, secrets)

    def is_in_family(self, family_name):
        """
        Method to check whether this service is part of a given family

        :param str family_name:
        :return: True/False
        :rtype: bool
        """
        return family_name in self.families

    def set_compute_resources(self, deployment):
        """
        Function to analyze the Docker Compose deploy attribute and set settings accordingly.
        deployment keys: replicas, mode, resources

        :param dict deployment: definition['deploy']
        """
        if keyisset("resources", deployment):
            resources = deployment["resources"]
        else:
            return
        cpu_alloc = 0
        cpu_resa = 0
        cpus = "cpus"
        memory = "memory"
        resa = "reservations"
        alloc = "limits"
        if keyisset(alloc, resources):
            cpu_alloc = (
                int(float(resources[alloc][cpus]) * 1024)
                if keyisset(cpus, resources[alloc])
                else 0
            )
            self.mem_alloc = (
                set_memory_to_mb(resources[alloc][memory].strip())
                if keyisset(memory, resources[alloc])
                else 0
            )
        if keyisset(resa, resources):
            cpu_resa = (
                int(float(resources[resa][cpus]) * 1024)
                if keyisset(cpus, resources[resa])
                else 0
            )
            self.mem_resa = (
                set_memory_to_mb(resources[resa][memory].strip())
                if keyisset(memory, resources[resa])
                else 0
            )
        self.cpu_amount = (
            max(cpu_resa, cpu_alloc) if (cpu_resa or cpu_alloc) else Ref(AWS_NO_VALUE)
        )
        if self.cpu_amount > 4096:
            LOG.warn("Fargate does not support more than 4 vCPU. Scaling down")
            self.cpu_amount = 4096

    def set_ecs_healthcheck(self):
        """
        Function to set healtcheck configuration
        :return:
        """
        if not self.healthcheck:
            self.ecs_healthcheck = Ref(AWS_NO_VALUE)
            return
        valid_keys = ["test", "interval", "timeout", "retries", "start_period"]
        attr_mappings = {
            "test": "Command",
            "interval": "Interval",
            "timeout": "Timeout",
            "retries": "Retries",
            "start_period": "StartPeriod",
        }
        required_keys = ["test"]
        validate_healthcheck(self.healthcheck, valid_keys, required_keys)
        params = {}
        for key in self.healthcheck.keys():
            params[attr_mappings[key]] = self.healthcheck[key]
        if isinstance(params["Command"], str):
            params["Command"] = [self.healthcheck["test"]]
        if keyisset("Interval", params) and isinstance(params["Interval"], str):
            params["Interval"] = int(self.healthcheck["interval"])
        self.ecs_healthcheck = HealthCheck(**params)

    def set_replicas(self, deployment):
        """
        Function to set the service deployment settings.
        """
        if keyisset("replicas", deployment):
            self.replicas = int(deployment["replicas"])

    def define_start_condition(self, deployment):
        """
        Method to define the start condition success for the container

        :param deployment:
        :return:
        """
        depends_key = "ecs.depends.condition"
        labels = "labels"
        allowed_values = ["START", "COMPLETE", "SUCCESS", "HEALTHY"]
        if not isinstance(self.ecs_healthcheck, Ref):
            LOG.warn(f"Healthcheck was defined on {self.name}. Overriding to HEALTHY")
            self.container_start_condition = "HEALTHY"
        elif keyisset(labels, deployment) and keyisset(depends_key, deployment[labels]):
            if deployment[labels][depends_key] not in allowed_values:
                raise ValueError(
                    f"Attribute {depends_key} is invalid. Must be one of",
                    allowed_values,
                )
            self.container_start_condition = deployment[labels][depends_key]

    def define_families(self, deployment):
        """
        Function to assign the service to a family / families
        :param deployment:
        :return:
        """
        labels = "labels"
        ecs_task_family = "ecs.task.family"
        if keyisset(labels, deployment) and keyisset(
            ecs_task_family, deployment[labels]
        ):
            if isinstance(deployment[labels][ecs_task_family], str):
                self.families = deployment[labels][ecs_task_family].split(",")
            else:
                raise TypeError(
                    f"{ecs_task_family} can only be one of ",
                    str,
                    "Got",
                    type(deployment[labels][ecs_task_family]),
                )
        else:
            self.families.append(self.logical_name)

    def set_service_deploy(self):
        """
        Function to setup the service configuration from the deploy section of the service in compose file.
        """
        deploy = "deploy"
        if not keyisset("deploy", self.definition):
            return
        self.define_families(self.definition[deploy])
        self.set_compute_resources(self.definition[deploy])
        self.set_replicas(self.definition[deploy])
        self.define_start_condition(self.definition[deploy])


def handle_same_task_services_dependencies(services_config):
    """
    Function to define inter-tasks dependencies

    :param list services_config:
    :return:
    """
    for service in services_config:
        LOG.debug(service[1].depends_on)
        LOG.debug(
            any(
                k in [j[1].name for j in services_config] for k in service[1].depends_on
            )
        )
        if service[1].depends_on and any(
            k in [j[1].name for j in services_config] for k in service[1].depends_on
        ):
            service[1].container_definition.Essential = False
            parents = [
                s_service[1]
                for s_service in services_config
                if s_service[1].name in service[1].depends_on
            ]
            parents_dependency = [
                {"ContainerName": p.name, "Condition": p.container_start_condition}
                for p in parents
            ]
            setattr(service[1].container_definition, "DependsOn", parents_dependency)
            for _ in parents:
                service[0] += 1


def assign_policy_to_role(role_secrets, role):
    """
    Function to assign the policy to role Policies
    :param list role_secrets:
    :param troposphere.iam.Role role:
    :return:
    """
    role_policy = Policy(
        PolicyName="AccessToPreDefinedSecrets",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Sid": "AllowSecretsAccess",
                    "Resource": [secret.aws_iam_name for secret in role_secrets],
                }
            ],
        },
    )
    if hasattr(role, "Policies") and isinstance(role.Policies, list):
        existing_policy_names = [
            policy.PolicyName for policy in getattr(role, "Policies")
        ]
        if role_policy.PolicyName not in existing_policy_names:
            role.Policies.append(role_policy)
    else:
        setattr(role, "Policies", [role_policy])


def assign_secrets_to_roles(secrets, exec_role, task_role):
    """
    Function to assign secrets access policies to exec_role and/or task_role

    :param secrets:
    :param exec_role:
    :param task_role:
    :return:
    """
    exec_role_secrets = [secret for secret in secrets if EXEC_ROLE_T in secret.links]
    task_role_secrets = [secret for secret in secrets if TASK_ROLE_T in secret.links]
    LOG.debug(exec_role_secrets)
    LOG.debug(task_role_secrets)
    for secret in secrets:
        if EXEC_ROLE_T not in secret.links:
            LOG.warn(
                f"You did not specify {EXEC_ROLE_T} in your LinksTo for this secret. You will not have ECS"
                "Expose the value of the secret to your container."
            )
    if exec_role_secrets:
        assign_policy_to_role(exec_role_secrets, exec_role)
    if task_role_secrets:
        assign_policy_to_role(task_role_secrets, task_role)


def add_policies(config, key, new_policies):
    existing_policies = config[key]
    existing_policy_names = [policy.PolicyName for policy in existing_policies]
    for count, policy in enumerate(new_policies):
        generated_name = (
            f"PolicyGenerated{count}"
            if f"PolicyGenerated{count}" not in existing_policy_names
            else f"PolicyGenerated{count+len(existing_policy_names)}"
        )
        name = generated_name if not keyisset("name", policy) else policy["name"]
        if name in existing_policy_names:
            return
        if not keyisset("document", policy):
            raise KeyError("You must set the policy document for the policy")
        if (
            keyisset("Version", policy["document"])
            and not isinstance(policy["document"]["Version"], str)
            or not keyisset("Version", policy["document"])
        ):
            policy["document"]["Version"] = "2012-10-17"
        policy_object = Policy(PolicyName=name, PolicyDocument=policy["document"])
        existing_policies.append(policy_object)


def handle_iam_boundary(config, key, new_value):
    """

    :param config: the IAM Config
    :param key: The key, here, boundary
    :param new_value:

    """
    if new_value.startswith("arn:aws"):
        config[key] = new_value
    else:
        config[key] = Sub(
            f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:policy/{new_value}"
        )


class ComposeFamily(object):
    """
    Class to group services logically to create the final ECS Service
    """

    def __init__(self, services, family_name):
        self.services = services
        self.ordered_services = []
        self.ignored_services = []
        self.name = family_name
        self.logical_name = re.sub(r"[^a-zA-Z0-9]+", "", family_name)
        self.iam = {"boundary": None, "managed_policies": [], "policies": []}
        self.template = None
        self.use_xray = None
        self.stack = None
        self.task_definition = None
        self.service_definition = None
        self.service_config = None
        self.scalable_target = None
        self.stack_parameters = {}
        self.set_xray()
        self.sort_container_configs()
        self.handle_iam()
        self.handle_logging()
        self.apply_services_params()

    def add_service(self, service):
        self.services.append(service)
        self.set_xray()
        self.refresh()

    def refresh(self):
        self.sort_container_configs()
        self.handle_iam()
        self.handle_logging()
        self.apply_services_params()

    def set_xray(self):
        self.use_xray = any(
            [keyisset("use_xray", service.x_configs) for service in self.services]
        )
        if self.use_xray is True and "xray-daemon" not in [
            service.name for service in self.services
        ]:
            xray_service = ComposeService(
                "xray-daemon",
                {
                    "image": AWS_XRAY_IMAGE,
                    "deploy": {
                        "resources": {"limits": {"cpus": 0.03125, "memory": "256M"}},
                    },
                    "x-configs": {
                        "iam": {
                            "managed_policies": [
                                "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
                            ]
                        }
                    },
                },
            )
            for service in self.services:
                service.depends_on.append(xray_service.name)
                LOG.debug(f"Adding xray-daemon as dependency to {service.name}")
            self.add_service(xray_service)
            if not xray_service.name not in self.ignored_services:
                self.ignored_services.append(xray_service)

    def reset_logging_retention_period(self, closest_valid):
        """
        Method to reset the logging retention period to the closest valid value.

        :param int closest_valid:
        :return:
        """
        for service in self.services:
            if service.x_configs:
                if keyisset("logging", service.x_configs):
                    service.x_configs["logging"][
                        "logs_retention_period"
                    ] = closest_valid
                else:
                    service.x_configs["logging"] = {
                        "logs_retention_period": closest_valid
                    }

    def handle_logging(self):
        x_logging = []
        for service in self.services:
            if service.x_configs and keyisset("logging", service.x_configs):
                x_logging.append(service.x_configs["logging"])
        periods = [
            config["logs_retention_period"]
            for config in x_logging
            if keyisset("logs_retention_period", config)
        ]
        if periods and max(periods) != LOG_GROUP_RETENTION.Default:
            closest_valid = min(
                ecs_params.LOG_GROUP_RETENTION.AllowedValues,
                key=lambda x: abs(x - max(periods)),
            )
            if closest_valid != max(periods):
                LOG.warn(
                    f"The days you set for logging was invalid ({max(periods)}). Adjusted to {closest_valid}"
                )
            self.reset_logging_retention_period(closest_valid)
            self.stack_parameters.update({LOG_GROUP_RETENTION.title: closest_valid})

    def sort_container_configs(self):
        """
        Method to sort out the containers dependencies and create the containers definitions based on the configs.
        :return:
        """
        service_configs = [[0, service] for service in self.services]
        handle_same_task_services_dependencies(service_configs)
        ordered_containers_config = sorted(service_configs, key=lambda i: i[0])
        self.ordered_services = [s[1] for s in ordered_containers_config]
        for service in self.ordered_services:
            service.container_definition.Essential = False
        ordered_containers_config[0][1].container_definition.Essential = True
        LOG.debug(service_configs, ordered_containers_config)
        LOG.debug(
            "Essentially",
            ordered_containers_config[0][1].name,
            ordered_containers_config[0][1].container_definition.Essential,
        )
        LOG.debug(
            dumps(
                [service.container_definition.to_dict() for service in self.services],
                indent=4,
            )
        )
        for service in self.services:
            self.stack_parameters.update(service.container_parameters)

    def sort_iam_settings(self, key, setting):
        """
        Method to sort out iam configuration

        :param tuple key:
        :param dict setting:
        :return:
        """
        if keyisset(key[0], setting) and isinstance(setting[key[0]], key[1]):
            if key[2]:
                key[2](self.iam, key[0], setting[key[0]])
            else:
                if key[1] is list and keypresent(key[0], self.iam):
                    self.iam[key[0]] = list(set(self.iam[key[0]] + setting[key[0]]))
                if key[1] is str and keypresent(key[0], self.iam):
                    self.iam[key[0]] = setting[key[0]]

    def handle_iam(self):
        valid_keys = [
            ("managed_policies", list, None),
            ("policies", list, add_policies),
            ("boundary", (str, Sub), handle_iam_boundary),
        ]
        iam_settings = [
            service.x_configs["iam"]
            for service in self.services
            if service.x_configs and keyisset("iam", service.x_configs)
        ]
        for setting in iam_settings:
            for key in valid_keys:
                self.sort_iam_settings(key, setting)
        self.set_secrets_access()

    def handle_permission_boundary(self, prop_key, cfn_key):
        if keyisset("boundary", self.iam) and self.template:
            if EXEC_ROLE_T in self.template.resources:
                setattr(
                    self.template.resources[EXEC_ROLE_T], cfn_key, self.iam[prop_key]
                )
            if TASK_ROLE_T in self.template.resources:
                setattr(
                    self.template.resources[TASK_ROLE_T], cfn_key, self.iam[prop_key]
                )

    def assign_iam_policies(self, role, prop):
        """
        Method to handle assignment of IAM policies defined from compose file.

        :param role:
        :param prop:
        :return:
        """
        if hasattr(role, prop[1]):
            existing = getattr(role, prop[1])
            existing_policy_names = [policy.PolicyName for policy in existing]
            for new_policy in self.iam[prop[0]]:
                if new_policy.PolicyName not in existing_policy_names:
                    existing.append(new_policy)
        else:
            setattr(role, prop[1], self.iam[prop[0]])

    def assign_iam_managed_policies(self, role, prop):
        """
        Method to assign managed policies to IAM role

        :param role:
        :param prop:
        :return:
        """
        if hasattr(role, prop[1]):
            setattr(
                role,
                prop[1],
                list(set(self.iam[prop[0]] + getattr(role, prop[1]))),
            )
        else:
            setattr(role, prop[1], self.iam[prop[0]])

    def assign_policies(self, role_name=None):
        """
        Method to assign IAM configuration (policies, boundary etc.) to the Task Role.
        Role can be overriden

        :param str role_name: The role LogicalName as defined in the template
        """
        if role_name is None:
            role_name = TASK_ROLE_T
        if not self.template or role_name not in self.template.resources:
            return
        role = self.template.resources[role_name]
        props = [
            (
                "managed_policies",
                "ManagedPolicyArns",
                list,
                self.assign_iam_managed_policies,
            ),
            ("policies", "Policies", list, self.assign_iam_policies),
            ("boundary", "PermissionsBoundary", (str, Sub), None),
        ]
        for prop in props:
            if keyisset(prop[0], self.iam) and isinstance(self.iam[prop[0]], prop[2]):
                if prop[0] == "boundary":
                    self.handle_permission_boundary(prop[0], prop[1])
                elif prop[3]:
                    prop[3](role, prop)

    def set_secrets_access(self):
        """
        Method to handle secrets permissions access
        """
        if (
            self.template
            and EXEC_ROLE_T in self.template.resources
            and TASK_ROLE_T in self.template.resources
        ):
            secrets = []
            for service in self.services:
                for secret in service.secrets:

                    secrets.append(secret)
            if secrets:
                assign_secrets_to_roles(
                    secrets,
                    self.template.resources[EXEC_ROLE_T],
                    self.template.resources[TASK_ROLE_T],
                )

    def set_task_compute_parameter(self):
        """
        Method to update task parameter for CPU/RAM profile
        """
        tasks_cpu = 0
        tasks_ram = 0
        for service in self.services:
            container = service.container_definition
            if isinstance(container.Cpu, int):
                tasks_cpu += container.Cpu
            if isinstance(container.Memory, int) and isinstance(
                container.MemoryReservation, int
            ):
                tasks_ram += max(container.Memory, container.MemoryReservation)
            elif isinstance(container.Memory, Ref) and isinstance(
                container.MemoryReservation, int
            ):
                tasks_ram += container.MemoryReservation
            elif isinstance(container.Memory, int) and isinstance(
                container.MemoryReservation, Ref
            ):
                tasks_ram += container.Memory
            else:
                LOG.warn(
                    f"{service.name} does not have RAM settings."
                    "Based on CPU, it will pick the smaller RAM Fargate supports"
                )
        if tasks_cpu > 0 or tasks_ram > 0:
            cpu_ram = find_closest_fargate_configuration(tasks_cpu, tasks_ram, True)
            LOG.debug(
                f"{self.logical_name} Task CPU: {tasks_cpu}, RAM: {tasks_ram} => {cpu_ram}"
            )
            self.stack_parameters.update({ecs_params.FARGATE_CPU_RAM_CONFIG_T: cpu_ram})

    def set_task_definition(self):
        """
        Function to set or update the task definition

        :param self: the self of services
        """
        self.task_definition = TaskDefinition(
            TASK_T,
            template=self.template,
            Cpu=ecs_params.FARGATE_CPU,
            Memory=ecs_params.FARGATE_RAM,
            NetworkMode=NETWORK_MODE,
            Family=Ref(ecs_params.SERVICE_NAME),
            TaskRoleArn=GetAtt(TASK_ROLE_T, "Arn"),
            ExecutionRoleArn=GetAtt(EXEC_ROLE_T, "Arn"),
            ContainerDefinitions=[s.container_definition for s in self.services],
            RequiresCompatibilities=["EC2", "FARGATE"],
            Tags=Tags(
                {
                    "Name": Ref(ecs_params.SERVICE_NAME),
                    "Environment": Ref(AWS_STACK_NAME),
                }
            ),
        )

    def apply_services_params(self):
        if not self.template:
            return
        for service in self.services:
            self.stack_parameters.update({service.image_param.title: service.image})
            if service.image_param.title not in self.template.parameters:
                self.template.add_parameter(service.image_param)

    def init_task_definition(self):
        add_service_roles(self.template)
        self.set_task_compute_parameter()
        self.set_task_definition()
