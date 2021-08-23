#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from copy import deepcopy
from json import dumps
from os import path

import docker
import requests
import urllib3
from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import (
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    AWS_STACK_NAME,
    FindInMap,
    GetAtt,
    If,
    Join,
    Ref,
    Sub,
    Tags,
)
from troposphere.ecs import (
    CapacityProviderStrategyItem,
    ContainerDefinition,
    DockerVolumeConfiguration,
    EnvironmentFile,
    EphemeralStorage,
    HealthCheck,
    KernelCapabilities,
    LinuxParameters,
    LogConfiguration,
    MountPoint,
    PortMapping,
    RepositoryCredentials,
)
from troposphere.ecs import Service as EcsService
from troposphere.ecs import SystemControl, TaskDefinition, Tmpfs, Ulimit, Volume
from troposphere.iam import Policy
from troposphere.logs import LogGroup

from ecs_composex.common import FILE_PREFIX, LOG, NONALPHANUM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, Parameter
from ecs_composex.common.compose_volumes import (
    ComposeVolume,
    handle_volume_dict_config,
    handle_volume_str_config,
)
from ecs_composex.common.files import upload_file
from ecs_composex.common.services_helpers import (
    define_ingress_mappings,
    import_env_variables,
    set_else_none,
    set_logging_expiry,
    validate_healthcheck,
)
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.docker_tools import (
    find_closest_fargate_configuration,
    import_time_values_to_seconds,
    set_memory_to_mb,
)
from ecs_composex.ecs.ecs_conditions import USE_FARGATE_CON_T
from ecs_composex.ecs.ecs_iam import add_service_roles
from ecs_composex.ecs.ecs_params import (
    AWS_XRAY_IMAGE,
    EXEC_ROLE_T,
    NETWORK_MODE,
    TASK_ROLE_T,
    TASK_T,
)
from ecs_composex.ecs.ecs_predefined_alarms import PREDEFINED_SERVICE_ALARMS_DEFINITION
from ecs_composex.iam import add_role_boundaries, define_iam_policy
from ecs_composex.secrets.compose_secrets import (
    ComposeSecret,
    match_secrets_services_config,
)
from ecs_composex.vpc.vpc_params import APP_SUBNETS

NUMBERS_REG = r"[^0-9.]"
MINIMUM_SUPPORTED = 4


class ComposeService(object):
    """
    Class to represent a service

    :cvar str container_name: name of the container to use in definitions
    """

    main_key = "services"
    keys = [
        ("build", (str, dict)),
        ("cap_add", list),
        ("cap_drop", list),
        ("cgroup_parent", str),
        ("command", (list, str)),
        ("configs", dict),
        ("container_name", str),
        ("credential_spec", str),
        ("depends_on", list),
        ("deploy", dict),
        ("devices", list),
        ("dns", (list, str)),
        ("dns_search", list),
        ("entrypoint", (str, list)),
        ("environment", (list, dict)),
        ("env_file", (list, str)),
        ("expose", list),
        ("external_links", list),
        ("extra_hosts", list),
        ("healthcheck", dict),
        ("hostname", str),
        ("labels", (dict, list)),
        ("logging", dict),
        ("links", list),
        ("network_mode", str),
        ("networks", (list, dict)),
        ("image", str),
        ("init", bool),
        ("isolation", str),
        ("pid", str),
        ("ports", list),
        ("privileged", bool),
        ("read_only", bool),
        ("restart", str),
        ("shm_size", str),
        ("security_opt", str),
        ("secrets", list),
        ("stop_signal", str),
        ("sysctls", (list, dict)),
        ("tmpfs", (str, list)),
        ("ulimits", dict),
        ("user", (int, str)),
        ("userns_mode", str),
        ("volumes", list),
        ("working_dir", str),
        ("x-configs", dict),
        ("x-logging", dict),
        ("x-iam", dict),
        ("x-xray", bool),
        ("x-scaling", dict),
        ("x-network", dict),
        ("x-alarms", dict),
        ("x-ecr", dict),
        ("x-prometheus", dict),
        ("x-docker_opts", dict),
        ("x-ecs", dict),
    ]

    ecs_plugin_aws_keys = [
        ("x-aws-role", dict),
        ("x-aws-policies", list),
        ("x-aws-autoscaling", dict),
        ("x-aws-pull_credentials", str),
        ("x-aws-logs_retention", int),
        ("x-aws-min_percent", int),
        ("x-aws-max_percent", int),
    ]

    def __init__(self, name, definition, volumes=None, secrets=None):
        if not isinstance(definition, dict):
            raise TypeError(
                "The definition of a service must be",
                dict,
                "got",
                type(definition),
            )
        if not all(
            key in [title[0] for title in self.ecs_plugin_aws_keys + self.keys]
            for key in list(definition.keys())
        ):
            raise KeyError(
                "Only valid keys for a service definition are",
                sorted([key[0] for key in self.keys]),
                sorted([key[0] for key in self.ecs_plugin_aws_keys]),
                "Got",
                sorted(list(definition.keys())),
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
        self.definition = deepcopy(definition)
        self.name = name
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.container_name = name
        self.service_name = Sub(f"${{{ROOT_STACK_NAME.title}}}-{self.name}")

        self.x_configs = set_else_none("x-configs", self.definition)
        self.x_scaling = set_else_none("x-scaling", self.definition, None, False)
        self.x_network = set_else_none("x-network", self.definition, None, False)
        self.x_iam = set_else_none("x-iam", self.definition)
        self.x_logging = {"RetentionInDays": 14}
        self.x_repo_credentials = None
        self.import_x_aws_settings()
        self.networks = {}
        self.replicas = 1
        self.container = None
        self.volumes = []
        self.logging = {}
        self.secrets = []
        self.env_files = []
        self.tmpfses = []
        self.ephemeral_storage = 0
        self.user = None
        self.group = None
        self.user_group = None
        self.code_profiler = None
        self.set_env_files()
        self.environment = set_else_none("environment", self.definition, None, False)
        self.cfn_environment = (
            import_env_variables(self.environment)
            if self.environment
            else Ref(AWS_NO_VALUE)
        )
        self.ports = set_else_none("ports", self.definition, [])
        self.depends_on = set_else_none("depends_on", self.definition, [], False)
        self.command = (
            definition["command"]
            if keyisset("command", definition)
            else Ref(AWS_NO_VALUE)
        )
        self.image = self.definition["image"]
        self.image_digest = None
        self.image_param = Parameter(
            f"{self.logical_name}ImageUrl", Default=self.image, Type="String"
        )
        self.deploy = set_else_none("deploy", self.definition, None)
        self.ingress_mappings = define_ingress_mappings(self.ports)
        self.mem_alloc = None
        self.mem_resa = None
        self.cpu_amount = None
        self.launch_type = ecs_params.LAUNCH_TYPE.Default
        self.families = []
        self.my_family = None
        self.is_aws_sidecar = False
        self.is_essential = True
        self.container_definition = None
        self.update_config = {}
        self.working_dir = set_else_none(
            "working_dir", self.definition, alt_value=Ref(AWS_NO_VALUE)
        )
        self.x_ecs = set_else_none("x-ecs", self.definition, None)
        self.capacity_provider_strategy = set_else_none(
            "CapacityProviderStrategy", self.x_ecs, None
        )

        self.container_start_condition = "START"
        self.healthcheck = set_else_none("healthcheck", self.definition, None)
        self.ecs_healthcheck = Ref(AWS_NO_VALUE)
        self.set_ecs_healthcheck()
        self.define_logging()
        self.container_parameters = {}

        self.set_user_group()
        self.map_volumes(volumes)
        self.map_secrets(secrets)
        self.define_families()
        self.set_service_deploy()
        self.set_container_definition()
        self.set_networks()
        self.ecr_config = set_else_none("x-ecr", self.definition, None)

    def retrieve_image_digest(self):
        valid_media_types = [
            "application/vnd.docker.distribution.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.docker.distribution.manifest.v1+prettyjws",
            "application/vnd.docker.distribution.manifest.list.v2+json",
        ]
        try:
            dkr_client = docker.APIClient()
            image_details = dkr_client.inspect_distribution(self.image)
            if not keyisset("Descriptor", image_details):
                raise KeyError(f"No information retrieved for {self.image}")
            details = image_details["Descriptor"]
            if (
                keyisset("mediaType", details)
                and details["mediaType"] not in valid_media_types
            ):
                raise ValueError(
                    "The mediaType is not valid. Got",
                    details["mediaType"],
                    "Expected one of",
                    valid_media_types,
                )
            if keyisset("digest", details):
                self.image_digest = details["digest"]
            else:
                LOG.warning(
                    "No digest found. This might be due to Registry API prior to V2"
                )

        except (docker.errors.APIError, docker.errors.DockerException) as error:
            LOG.error(f"Failed to retrieve the image digest for {self.image}")
            print(error)
        except (FileNotFoundError, urllib3.exceptions, requests.exceptions):
            LOG.error("Failed to connect to any docker engine.")

    def define_port_mappings(self):
        """
        Method to determine the list of port mappings to use for either AWS VPC deployments or else (bridge etc).
        Not in use atm as AWS VPC is made mandatory
        """
        ec2_mappings = []
        aws_vpc_mappings = []
        for c_port, h_ports in self.ingress_mappings.items():
            for port in h_ports:
                ec2_mappings.append(PortMapping(ContainerPort=c_port, HostPort=port))
        for port in self.ingress_mappings.keys():
            aws_vpc_mappings = [
                PortMapping(ContainerPort=port, HostPort=port)
                for port in self.ingress_mappings.keys()
            ]
        return aws_vpc_mappings, ec2_mappings

    def import_docker_labels(self):
        """
        Method to import the Docker labels if defined
        """
        labels = {}
        if not keyisset("labels", self.definition):
            return labels
        else:
            if isinstance(self.definition["labels"], dict):
                return self.definition["labels"]
            elif isinstance(self.definition["labels"], list):
                for label in self.definition["labels"]:
                    splits = label.split("=")
                    labels.update({splits[0]: splits[1] if len(splits) == 2 else ""})
        return labels

    def set_container_definition(self):
        """
        Function to define the container definition matching the service definition
        """
        secrets = [secret for secrets in self.secrets for secret in secrets.ecs_secret]
        ports_mappings = self.define_port_mappings()
        self.define_compose_logging()
        self.container_definition = ContainerDefinition(
            Image=Ref(self.image_param),
            Name=self.name,
            Cpu=self.cpu_amount if self.cpu_amount else Ref(AWS_NO_VALUE),
            Memory=self.mem_alloc if self.mem_alloc else Ref(AWS_NO_VALUE),
            MemoryReservation=self.mem_resa if self.mem_resa else Ref(AWS_NO_VALUE),
            PortMappings=ports_mappings[0] if self.ports else Ref(AWS_NO_VALUE),
            Environment=self.cfn_environment,
            LogConfiguration=self.logging,
            Command=self.command,
            HealthCheck=self.ecs_healthcheck,
            DependsOn=Ref(AWS_NO_VALUE),
            Essential=self.is_essential,
            Secrets=secrets,
            Ulimits=self.define_ulimits(),
            LinuxParameters=LinuxParameters(
                Capabilities=self.define_kernel_options(),
                SharedMemorySize=self.define_shm_size(),
                Tmpfs=self.define_tmpfs(),
            ),
            Privileged=If(
                USE_FARGATE_CON_T,
                Ref(AWS_NO_VALUE),
                keyisset("Privileged", self.definition),
            ),
            WorkingDirectory=self.working_dir,
            DockerLabels=self.import_docker_labels(),
            ReadonlyRootFilesystem=keyisset("read_only", self.definition),
            SystemControls=self.define_sysctls(),
            User=self.user_group if self.user_group else Ref(AWS_NO_VALUE),
        )
        self.container_parameters.update({self.image_param.title: self.image})

    def define_compose_logging(self):
        """
        Method to define logging for service.
        """
        default = LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Sub(
                    f"${{{ROOT_STACK_NAME.title}}}/svc/ecs/{self.logical_name}"
                ),
                "awslogs-region": Ref(AWS_REGION),
                "awslogs-stream-prefix": self.name,
            },
        )
        if not keyisset("logging", self.definition) or (
            keyisset("logging", self.definition)
            and not keyisset("driver", self.definition["logging"])
        ):
            self.logging = default
            return
        logging_def = self.definition["logging"]
        valid_drivers = ["awslogs"]
        if not logging_def["driver"] in valid_drivers:
            LOG.warning(
                "The logging driver",
                logging_def["driver"],
                "is not supported. Only supported are",
                valid_drivers,
            )
            self.logging = default
        elif logging_def["driver"] == "awslogs" and keyisset("options", logging_def):
            options_def = logging_def["options"]
            options = {
                "awslogs-group": set_else_none(
                    "awslogs-group", options_def, alt_value=self.logical_name
                ),
                "awslogs-region": set_else_none(
                    "awslogs-region", options_def, alt_value=Ref(AWS_REGION)
                ),
                "awslogs-stream-prefix": set_else_none(
                    "awslogs-stream-prefix", options_def, alt_value=self.name
                ),
                "awslogs-endpoint": set_else_none(
                    "awslogs-endpoint", options_def, alt_value=Ref(AWS_NO_VALUE)
                ),
                "awslogs-datetime-format": set_else_none(
                    "awslogs-datetime-format",
                    options_def,
                    alt_value=Ref(AWS_NO_VALUE),
                ),
                "awslogs-multiline-pattern": set_else_none(
                    "awslogs-multiline-pattern",
                    options_def,
                    alt_value=Ref(AWS_NO_VALUE),
                ),
                "mode": set_else_none("mode", options_def, alt_value=Ref(AWS_NO_VALUE)),
                "max-buffer-size": set_else_none(
                    "max-buffer-size", options_def, alt_value=Ref(AWS_NO_VALUE)
                ),
            }
            if keypresent("awslogs-create-group", options_def) and isinstance(
                options_def["awslogs-create-group"], bool
            ):
                options["awslogs-create-group"] = keyisset(
                    "awslogs-create-group", options_def
                )
            elif keypresent("awslogs-create-group", options_def) and isinstance(
                options_def["awslogs-create-group"], str
            ):
                options["awslogs-create-group"] = options_def[
                    "awslogs-create-group"
                ] in [
                    "yes",
                    "true",
                    "Yes",
                    "True",
                ]
            self.logging = LogConfiguration(
                LogDriver="awslogs",
                Options=options,
            )

    def define_tmpfs(self):
        """
        Method to define the tmpfs settings
        """
        tmpfs_key = "tmpfs"
        if not keyisset(tmpfs_key, self.definition) and not self.tmpfses:
            return Ref(AWS_NO_VALUE)
        elif keyisset(tmpfs_key, self.definition):
            if isinstance(self.definition[tmpfs_key], str):
                self.tmpfses.append({"ContainerPath": self.definition[tmpfs_key]})
            elif isinstance(self.definition[tmpfs_key], list):
                for pathes in self.definition[tmpfs_key]:
                    self.tmpfses.append({"ContainerPath": pathes})
        rendered_fs = [Tmpfs(**args) for args in self.tmpfses]
        return If(USE_FARGATE_CON_T, Ref(AWS_NO_VALUE), rendered_fs)

    def define_sysctls(self):
        """
        Method to define the SystemControls
        """
        sysctls_key = "sysctls"
        if not keyisset(sysctls_key, self.definition):
            return Ref(AWS_NO_VALUE)
        def_dict = {}
        if isinstance(self.definition[sysctls_key], list):
            for prop in self.definition[sysctls_key]:
                splits = prop.split(r"=")
                if not splits or len(splits) != 2:
                    raise ValueError(f"Property define {prop} is not valid.")
                def_dict[splits[0]] = splits[1]
        elif isinstance(self.definition[sysctls_key], dict):
            def_dict = self.definition[sysctls_key]
        controls = []
        for name, value in def_dict.items():
            controls.append(SystemControl(Namespace=name, Value=str(value)))
        return If(USE_FARGATE_CON_T, Ref(AWS_NO_VALUE), controls)

    def define_shm_size(self):
        """
        Method to import and determine SHM SIZE
        """
        if not keyisset("shm_size", self.definition):
            return Ref(AWS_NO_VALUE)
        memory_value = set_memory_to_mb(self.definition["shm_size"])
        return If(USE_FARGATE_CON_T, Ref(AWS_NO_VALUE), memory_value)

    def set_add_capacities(self, add_key, valid, cap_adds, all_adds, fargate):
        """
        Method to set the kernel capacities to add

        :param str add_key:
        :param list valid:
        :param list cap_adds:
        :param list all_adds:
        :param list fargate:
        """
        if keyisset(add_key, self.definition):
            for capacity in self.definition[add_key]:
                if capacity not in valid:
                    raise ValueError(
                        f"Linux kernel capacity {capacity} is not supported in ECS or simply not valid"
                    )
                if capacity in fargate:
                    cap_adds.append(capacity)
                else:
                    all_adds.append(capacity)

    def set_drop_capacities(
        self, drop_key, valid, cap_adds, all_adds, all_drops, fargate
    ):
        """
        Method to set the drop kernel capacities

        :param str drop_key:
        :param list valid:
        :param list cap_adds:
        :param list all_adds:
        :param list all_drops:
        :param list fargate:
        """
        if keyisset(drop_key, self.definition):
            for capacity in self.definition[drop_key]:
                if capacity not in valid:
                    raise ValueError(
                        f"Linux kernel capacity {capacity} is not supported in ECS or simply not valid"
                    )
                if capacity in all_adds or capacity in cap_adds:
                    raise KeyError(
                        f"Capacity {capacity} already detected in cap_add. "
                        "You cannot both add and remove the capacity"
                    )
                if capacity in fargate:
                    cap_adds.append(capacity)
                else:
                    all_drops.append(capacity)

    def define_kernel_options(self):
        """
        Method to define and return the kernel option settings for cap_add and cap_drop
        :return:
        """
        valid = [
            "ALL",
            "AUDIT_CONTROL",
            "AUDIT_WRITE",
            "BLOCK_SUSPEND",
            "CHOWN",
            "DAC_OVERRIDE",
            "DAC_READ_SEARCH",
            "FOWNER",
            "FSETID",
            "IPC_LOCK",
            "IPC_OWNER",
            "KILL",
            "LEASE",
            "LINUX_IMMUTABLE",
            "MAC_ADMIN",
            "MAC_OVERRIDE",
            "MKNOD",
            "NET_ADMIN",
            "NET_BIND_SERVICE",
            "NET_BROADCAST",
            "NET_RAW",
            "SETFCAP",
            "SETGID",
            "SETPCAP",
            "SETUID",
            "SYS_ADMIN",
            "SYS_BOOT",
            "SYS_CHROOT",
            "SYS_MODULE",
            "SYS_NICE",
            "SYS_PACCT",
            "SYS_PTRACE",
            "SYS_RAWIO",
            "SYS_RESOURCE",
            "SYS_TIME",
            "SYS_TTY_CONFIG",
            "SYSLOG",
            "WAKE_ALARM",
        ]
        fargate = ["SYS_PTRACE"]
        add_key = "cap_add"
        drop_key = "cap_drop"
        cap_adds = []
        cap_drops = []
        all_adds = []
        all_drops = []
        if not keyisset(add_key, self.definition) and not keyisset(
            drop_key, self.definition
        ):
            return Ref(AWS_NO_VALUE)

        self.set_add_capacities(add_key, valid, cap_adds, all_adds, fargate)
        self.set_drop_capacities(
            drop_key, valid, cap_adds, all_adds, all_drops, fargate
        )
        kwargs = {
            "Add": cap_adds or Ref(AWS_NO_VALUE),
            "Drop": cap_drops or Ref(AWS_NO_VALUE),
        }
        if all_adds:
            cap_adds.append(If(USE_FARGATE_CON_T, Ref(AWS_NO_VALUE), all_adds))
        if all_drops:
            cap_drops.append(If(USE_FARGATE_CON_T, Ref(AWS_NO_VALUE), all_drops))
        return KernelCapabilities(**kwargs)

    def define_ulimits(self):
        """
        Method to set the ulimits
        """
        if not keyisset("ulimits", self.definition):
            return Ref(AWS_NO_VALUE)
        limits = self.definition["ulimits"]
        rendered_limits = []
        fargate_supported = ["nofile"]
        allowed = [
            "core",
            "cpu",
            "data",
            "fsize",
            "locks",
            "memlock",
            "msgqueue",
            "nice",
            "nofile",
            "nproc",
            "rss",
            "rtprio",
            "rttime",
            "sigpending",
            "stack",
        ]
        for limit_name, limit_value in limits.items():
            if limit_name not in allowed:
                raise KeyError(
                    f"Ulimit property {limit_name} is not supported by ECS. Valid ones are",
                    allowed,
                )
            elif isinstance(limit_value, (str, int)):
                ulimit = Ulimit(
                    SoftLimit=int(limit_value),
                    HardLimit=int(limit_value),
                    Name=limit_name,
                )
            elif (
                isinstance(limit_value, dict)
                and keyisset("soft", limit_value)
                and keyisset("hard", limit_value)
            ):
                ulimit = Ulimit(
                    SoftLimit=int(limit_value["soft"]),
                    HardLimit=int(limit_value["hard"]),
                    Name=limit_name,
                )
            elif isinstance(limit_value, dict) and not (
                keyisset("soft", limit_value) and keyisset("hard", limit_value)
            ):
                raise KeyError(
                    f"Missing hard or soft properties for ulimit {limit_name}"
                )
            else:
                raise TypeError("ulimit is not of the proper definition")
            if limit_name not in fargate_supported:
                rendered_limits.append(If(USE_FARGATE_CON_T, Ref(AWS_NO_VALUE), ulimit))
            else:
                rendered_limits.append(ulimit)
        if rendered_limits:
            return rendered_limits
        return Ref(AWS_NO_VALUE)

    def set_user_group(self):
        """
        Method to assign the user / group IDs for the container
        """
        if not keyisset("user", self.definition):
            return
        user_value = self.definition["user"]
        if isinstance(user_value, int):
            self.user = str(user_value)
        elif isinstance(user_value, str):
            valid_pattern = re.compile(r"^\d{1,5}$|(^\d{1,5})(?::)(\d{1,5})$")
            if not valid_pattern.match(user_value):
                raise ValueError(
                    "user property must be of the format", valid_pattern.pattern
                )
            groups = valid_pattern.match(user_value).groups()
            self.user = groups[0]
            if len(groups) == 2:
                self.group = groups[-1]
        self.user_group = self.user
        if self.group:
            self.user_group = f"{self.user}:{self.group}"

    def set_env_files(self):
        """
        Method to list all the env files and check the files are found and available.
        """
        env_file_key = "env_file"
        if not keyisset(env_file_key, self.definition):
            return
        if isinstance(self.definition[env_file_key], str):
            file_path = self.definition[env_file_key]
            if not path.exists(path.abspath(file_path)):
                raise FileNotFoundError("No file found at", path.abspath(file_path))
            self.env_files.append(path.abspath(file_path))
        elif isinstance(self.definition[env_file_key], list):
            for file_path in self.definition[env_file_key]:
                if not isinstance(file_path, str):
                    raise TypeError(
                        "Files in the env_file is supposed to be a list of paths to files (str). Got",
                        type(file_path),
                    )
                if not path.exists(path.abspath(file_path)):
                    raise FileNotFoundError("No file found at", path.abspath(file_path))
                self.env_files.append(path.abspath(file_path))
        LOG.debug(self.env_files)

    def set_networks(self):
        if not keyisset("networks", self.definition):
            return
        if isinstance(self.definition["networks"], list):
            for name in self.definition["networks"]:
                self.networks[name] = None
        elif isinstance(self.definition["networks"], dict):
            self.networks.update(self.definition["networks"])

    def merge_x_aws_role(self, key):
        """
        Method to update the service definition with the x-aws-role information if NOT defined in the composex
        definition.

        :param str key:
        """
        policy_def = {
            "PolicyName": "ImportedFromXAWSRole",
            "PolicyDocument": self.definition[key],
        }
        if not self.x_iam:
            self.x_iam = {"Policies": [policy_def]}
            LOG.info(f"Added {key} definition")
        elif self.x_iam and keyisset("Policies", self.x_iam):
            self.x_iam["Policies"].append(policy_def)
            LOG.info(f"Merged {key} to existing definition")

    def merge_x_policies(self, key):
        """
        Method to merge policies

        :param str key:
        """
        if not self.x_iam:
            self.x_iam = {"ManagedPolicyArns": self.definition[key]}
            LOG.info(f"Added {key} definition")
        elif self.x_iam and keyisset("ManagedPolicyArns", self.x_iam):
            self.x_iam["ManagedPolicyArns"] += self.definition[key]
            LOG.info(f"Merged {key} definition")

    def set_x_credentials_secret(self, key):
        """
        Method that will set the secret associated to the service to retrieve the docker image if defined through
        x-aws-pull_credentials
        """
        if not keyisset(key, self.definition):
            return
        self.x_repo_credentials = self.definition[key]

    def import_x_aws_settings(self):
        aws_keys = [
            ("x-aws-role", dict, self.merge_x_aws_role),
            ("x-aws-policies", list, self.merge_x_policies),
            ("x-aws-autoscaling", dict, None),
            ("x-aws-pull_credentials", str, self.set_x_credentials_secret),
        ]
        for setting in aws_keys:
            if keyisset(setting[0], self.definition) and not isinstance(
                self.definition[setting[0]], setting[1]
            ):
                raise TypeError(
                    f"{setting[0]} is of type",
                    type(self.definition[setting[0]]),
                    "Expected",
                    setting[1],
                )
            elif keyisset(setting[0], self.definition) and setting[2]:
                setting[2](setting[0])

    def define_logging(self):
        """
        Method to define logging properties
        """
        if keyisset("x-logging", self.definition):
            self.x_logging = self.definition["x-logging"]
        if keyisset("x-aws-logs_retention", self.definition) and keyisset(
            "RetentionInDays", self.x_logging
        ):
            self.x_logging["RetentionInDays"] = max(
                int(self.definition["x-aws-logs_retention"]),
                int(self.x_logging["RetentionInDays"]),
            )
        elif keyisset("x-aws-logs_retention", self.definition) and not keyisset(
            "RetentionInDays", self.x_logging
        ):
            self.x_logging["RetentionInDays"] = int(
                self.definition["x-aws-logs_retention"]
            )

    def map_volumes(self, volumes=None):
        """
        Method to apply mapping of volumes to the service and define the mapping configuration

        :param list volumes:
        :return:
        """
        if keyisset(ComposeVolume.main_key, self.definition):
            for s_volume in self.definition[ComposeVolume.main_key]:
                if (
                    isinstance(s_volume, dict)
                    and (keyisset("type", s_volume) and s_volume["type"] == "tmpfs")
                    or keyisset("tmpfs", s_volume)
                ):
                    tmpfs_def = {}
                    if not keyisset("target", s_volume):
                        raise KeyError(
                            "When defining tmpfs as volume, you must define a target"
                        )
                    tmpfs_def["ContainerPath"] = s_volume["target"]
                    if (
                        keyisset("tmpfs", s_volume)
                        and isinstance(s_volume["tmpfs"], dict)
                        and keyisset("size", s_volume["tmpfs"])
                    ):
                        tmpfs_def["Size"] = int(s_volume["tmpfs"]["size"])
                    self.tmpfses.append(tmpfs_def)
                else:
                    if not volumes:
                        continue
                    if isinstance(s_volume, str):
                        handle_volume_str_config(self, s_volume, volumes)
                    elif isinstance(s_volume, dict):
                        handle_volume_dict_config(self, s_volume, volumes)

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
        if not keyisset("resources", deployment):
            return
        resources = deployment["resources"]
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
        if isinstance(self.cpu_amount, int) and self.cpu_amount > 4096:
            LOG.warning("Fargate does not support more than 4 vCPU. Scaling down")
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
            "test": ("Command", None),
            "interval": ("Interval", import_time_values_to_seconds),
            "timeout": ("Timeout", import_time_values_to_seconds),
            "retries": ("Retries", None),
            "start_period": ("StartPeriod", import_time_values_to_seconds),
        }
        required_keys = ["test"]
        validate_healthcheck(self.healthcheck, valid_keys, required_keys)
        params = {}
        for key, value in self.healthcheck.items():
            ecs_key = attr_mappings[key][0]
            params[ecs_key] = value
            if attr_mappings[key][1] is not None:
                params[ecs_key] = attr_mappings[key][1](self.healthcheck[key])
        if isinstance(params["Command"], str):
            params["Command"] = [params["Command"]]
        self.ecs_healthcheck = HealthCheck(**params)

    def set_replicas(self, deployment):
        """
        Function to set the service deployment settings.
        """
        if keyisset("replicas", deployment):
            self.replicas = int(deployment["replicas"])

    def define_essential(self, deployment):
        """
        Method to define whether the container is essential.
        :param dict deployment:
        """
        essential_key = "ecs.essential"
        labels = "labels"
        positive_values = [True, "yes", "True"]
        negative_values = [False, "no", "False"]
        if keyisset(labels, deployment) and keyisset(essential_key, deployment[labels]):
            if (
                deployment[labels][essential_key] not in positive_values
                or deployment[labels][essential_key] not in negative_values
            ):
                raise ValueError(
                    "The values allowed for",
                    essential_key,
                    "are",
                    positive_values,
                    negative_values,
                    "Got",
                    deployment[labels][essential_key],
                )
            if deployment[labels][essential_key] in negative_values:
                self.is_essential = False

    def define_ephemeral_storage_condition(self, deployment):
        """
        Method to define the start condition success for the container

        :param deployment:
        :return:
        """
        storage_key = "ecs.ephemeral.storage"
        labels = "labels"
        if not keyisset(labels, deployment) or (
            keyisset(labels, deployment)
            and not keyisset(storage_key, deployment[labels])
        ):
            return
        storage_value = deployment[labels][storage_key]
        if isinstance(storage_value, (int, float)):
            ephemeral_storage = int(storage_value)
        elif isinstance(storage_value, str):
            ephemeral_storage = int(set_memory_to_mb(storage_value) / 1024)
        else:
            raise TypeError(
                f"The value for {storage_key} is of type",
                type(storage_value),
                "Expected one of",
                [int, float, str],
            )
        if ephemeral_storage < 21:
            LOG.warning(
                f"{self.name} - {storage_key}={ephemeral_storage} is smaller than 20(GB). Ignoring."
            )
        elif ephemeral_storage > 200:
            LOG.warning(
                f"{self.name} - {storage_key}={ephemeral_storage} is bigger than 200(GB). Setting to 200"
            )
            self.ephemeral_storage = 200
        else:
            self.ephemeral_storage = int(ephemeral_storage)
            LOG.info(f"{self.name} - {storage_key} set to {self.ephemeral_storage}")

    def define_compute_platform(self, deployment):
        """
        Determines whether to use ECS with EC2 or Fargate

        :param dict deployment:
        """
        compute_key = "ecs.compute.platform"
        launch_key = "ecs.launch.type"
        labels = "labels"
        allowed_values = ecs_params.LAUNCH_TYPE.AllowedValues
        if keyisset(labels, deployment) and keyisset(compute_key, deployment[labels]):
            value = deployment[labels][compute_key]
        elif keyisset(labels, deployment) and keyisset(launch_key, deployment[labels]):
            value = deployment[labels][launch_key]
        else:
            return
        if value not in allowed_values:
            raise ValueError(
                f"ecs.compute.platform is {deployment[labels][compute_key]}"
                "Must be one of",
                allowed_values,
            )
        self.launch_type = value
        LOG.info(
            f"{self.name} - {ecs_params.LAUNCH_TYPE.title} set to {self.launch_type}"
        )

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
            LOG.warning(
                f"Healthcheck was defined on {self.name}. Overriding to HEALTHY"
            )
            self.container_start_condition = "HEALTHY"
            if not self.is_essential:
                self.is_essential = True
        elif keyisset(labels, deployment) and keyisset(depends_key, deployment[labels]):
            if deployment[labels][depends_key] not in allowed_values:
                raise ValueError(
                    f"Attribute {depends_key} is invalid. Must be one of",
                    allowed_values,
                )
            self.container_start_condition = deployment[labels][depends_key]

    def define_families(self):
        """
        Function to assign the service to a family / families
        :param deployment:
        :return:
        """
        deploy = "deploy"
        labels = "labels"
        ecs_task_family = "ecs.task.family"
        deployment = {}
        if keyisset(deploy, self.definition):
            deployment = self.definition[deploy]
        if (
            deployment
            and keyisset(labels, deployment)
            and keyisset(ecs_task_family, deployment[labels])
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
            self.families.append(self.name)

    def set_update_config(self, deployment):
        """
        Method to set the update_config from the deploy service keys

        :param dict deployment:
        :return:
        """
        key = "update_config"
        if not keyisset(key, deployment):
            return
        if not isinstance(deployment[key], dict):
            raise TypeError(
                "The deploy.update_config must be a dict/map. Got",
                type(deployment[key]),
            )
        self.update_config = deployment[key]

    def set_service_deploy(self):
        """
        Function to setup the service configuration from the deploy section of the service in compose file.
        """
        deploy = "deploy"
        if not keyisset("deploy", self.definition):
            return
        self.set_compute_resources(self.definition[deploy])
        self.set_replicas(self.definition[deploy])
        self.define_start_condition(self.definition[deploy])
        self.define_compute_platform(self.definition[deploy])
        self.define_essential(self.definition[deploy])
        self.set_update_config(self.definition[deploy])
        self.define_ephemeral_storage_condition(self.definition[deploy])


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
                {
                    "ContainerName": p.name,
                    "Condition": p.container_start_condition,
                }
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

    secrets_list = [secret.iam_arn for secret in role_secrets]
    secrets_kms_keys = [secret.kms_key_arn for secret in role_secrets if secret.kms_key]
    secrets_statement = {
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue"],
        "Sid": "AllowSecretsAccess",
        "Resource": [secret for secret in secrets_list],
    }
    secrets_keys_statement = {}
    if secrets_kms_keys:
        secrets_keys_statement = {
            "Effect": "Allow",
            "Action": ["kms:Decrypt"],
            "Sid": "AllowSecretsKmsKeyDecrypt",
            "Resource": [kms_key for kms_key in secrets_kms_keys],
        }
    role_policy = Policy(
        PolicyName="AccessToPreDefinedSecrets",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [secrets_statement],
        },
    )
    if secrets_keys_statement:
        role_policy.PolicyDocument["Statement"].append(secrets_keys_statement)

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
            LOG.warning(
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
            else f"PolicyGenerated{count + len(existing_policy_names)}"
        )
        name = (
            generated_name
            if not keyisset("PolicyName", policy)
            else policy["PolicyName"]
        )
        if name in existing_policy_names:
            return
        if not keyisset("PolicyDocument", policy):
            raise KeyError("You must set the policy document for the policy")
        if (
            keyisset("Version", policy["PolicyDocument"])
            and not isinstance(policy["PolicyDocument"]["Version"], str)
            or not keyisset("Version", policy["PolicyDocument"])
        ):
            policy["PolicyDocument"]["Version"] = "2012-10-17"
        policy_object = Policy(PolicyName=name, PolicyDocument=policy["PolicyDocument"])
        existing_policies.append(policy_object)


def handle_iam_boundary(config, key, new_value):
    """

    :param config: the IAM Config
    :param key: The key, here, boundary
    :param new_value:

    """
    config[key] = define_iam_policy(new_value)


def identify_repo_credentials_secret(settings, task, secret_name):
    """
    Function to identify the secret_arn
    :param settings:
    :param ComposeFamily task:
    :param secret_name:
    :return:
    """
    secret_arn = None
    for secret in settings.secrets:
        if secret.name == secret_name:
            secret_arn = secret.arn
            if secret_name not in [s.name for s in settings.secrets]:
                raise KeyError(
                    f"secret {secret_name} was not found in the defined secrets",
                    [s.name for s in settings.secrets],
                )
            if secret.kms_key_arn:
                task.exec_role.Policies.append(
                    Policy(
                        PolicyName="RepositoryCredsKmsKeyAccess",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": ["kms:Decrypt"],
                                    "Resource": [secret.kms_key_arn],
                                }
                            ],
                        },
                    )
                )
            return secret_arn
    return None


class ComposeFamily(object):
    """
    Class to group services logically to create the final ECS Service
    """

    default_launch_type = "FARGATE"

    def __init__(self, services, family_name):
        self.services = services
        self.ordered_services = []
        self.ignored_services = []
        self.name = family_name
        self.logical_name = re.sub(r"[^a-zA-Z0-9]+", "", family_name)
        self.iam = {
            "PermissionsBoundary": None,
            "ManagedPolicyArns": [],
            "Policies": [],
        }
        self.services_depends_on = []
        self.deployment_config = {}
        self.template = None
        self.use_xray = None
        self.stack = None
        self.task_definition = None
        self.service_definition = None
        self.service_config = None
        self.task_ephemeral_storage = 0
        self.exec_role = None
        self.task_role = None
        self.scalable_target = None
        self.ecs_service = None
        self.launch_type = self.default_launch_type
        self.ecs_capacity_providers = []
        self.set_compute_platform()
        self.task_logging_options = {}
        self.stack_parameters = {}
        self.alarms = {}
        self.predefined_alarms = {}
        self.set_initial_services_dependencies()
        self.set_xray()
        self.sort_container_configs()
        self.handle_iam()
        self.apply_services_params()

    def add_service(self, service):
        self.services.append(service)
        if self.task_definition and service.container_definition:
            self.task_definition.ContainerDefinitions.append(
                service.container_definition
            )
            self.set_secrets_access()
        self.set_xray()
        self.set_task_ephemeral_storage()
        self.refresh()

    def refresh(self):
        self.sort_container_configs()
        self.set_compute_platform()
        self.merge_capacity_providers()
        self.handle_iam()
        self.handle_logging()
        self.apply_services_params()
        self.set_task_compute_parameter()

    def set_initial_services_dependencies(self):
        """
        Method to iterate over each depends_on service set in the family services and add them up

        :return:
        """
        for service in self.services:
            if service.depends_on:
                for service_depends_on in service.depends_on:
                    if service_depends_on not in self.services_depends_on:
                        self.services_depends_on.append(service_depends_on)

    def set_task_ephemeral_storage(self):
        """
        If any service ephemeral storage is defined above, sets the ephemeral storage to the maximum of them.
        """
        max_storage = max([service.ephemeral_storage for service in self.services])
        if max_storage >= 21:
            self.task_ephemeral_storage = max_storage

    def set_compute_platform(self):
        """
        Iterates over all services and if ecs.compute.platform
        :return:
        """
        if self.launch_type != self.default_launch_type:
            LOG.warning(
                f"{self.name} - The compute platform is already overridden to {self.launch_type}"
            )
            if self.stack:
                self.stack.Parameters.update({ecs_params.LAUNCH_TYPE: self.launch_type})
            for service in self.services:
                setattr(service, "compute_platform", self.launch_type)
        elif not all(
            service.launch_type == self.launch_type for service in self.services
        ):
            for service in self.services:
                if service.launch_type != self.launch_type:
                    platform = service.launch_type
                    LOG.info(
                        f"{self.name} - At least one service is defined not to be on FARGATE."
                        f" Overriding to {platform}"
                    )
                    self.launch_type = platform
                    if self.stack:
                        self.stack.Parameters.update(
                            {ecs_params.LAUNCH_TYPE: self.launch_type}
                        )

    def set_xray(self):
        """
        Automatically adds the xray-daemon sidecar to the task definition.
        """
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
                    "x-iam": {
                        "ManagedPolicyArns": [
                            "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
                        ]
                    },
                },
            )
            xray_service.is_aws_sidecar = True
            for service in self.services:
                service.depends_on.append(xray_service.name)
                LOG.debug(f"Adding xray-daemon as dependency to {service.name}")
            self.add_service(xray_service)
            if xray_service.name not in self.ignored_services:
                self.ignored_services.append(xray_service)

    def define_predefined_alarm_settings(self, new_settings):
        """
        Method to define the predefined alarm settings based on the alarm characteristics

        :param new_settings:
        :return:
        """
        for alarm_name, alarm_def in new_settings["Alarms"].items():
            if not keyisset("Properties", alarm_def):
                continue
            props = alarm_def["Properties"]
            if not keyisset("MetricName", props):
                raise KeyError("You must define a MetricName for the pre-defined alarm")
            metric_name = props["MetricName"]
            if metric_name == "RunningTaskCount":
                range_key = "max"
                if keyisset("range_key", new_settings):
                    range_key = new_settings["range_key"]
                new_settings["Settings"][
                    metric_name
                ] = self.service_config.scaling.scaling_range[range_key]

    def define_predefined_alarms(self):
        """
        Method to define which predefined alarms are available
        :return: dict of the alarms
        :rtype: dict
        """

        finalized_alarms = {}
        for name, settings in PREDEFINED_SERVICE_ALARMS_DEFINITION.items():
            if (
                keyisset("requires_scaling", settings)
                and not self.service_config.scaling.defined
            ):
                LOG.error(
                    f"No scaling range was defined for the service and rule {name} requires it. Skipping"
                )
                continue
            new_settings = deepcopy(settings)
            self.define_predefined_alarm_settings(new_settings)
            finalized_alarms[name] = new_settings
        return finalized_alarms

    def validate_service_predefined_alarms(self, valid_predefined, service_predefined):
        if not all(
            name in valid_predefined.keys() for name in service_predefined.keys()
        ):
            raise KeyError(
                f"For {self.logical_name}, only valid service_predefined alarms are",
                valid_predefined.keys(),
                "Got",
                service_predefined.keys(),
            )

    def define_default_alarm_settings(self, key, value, settings_key, valid_predefined):
        if not keyisset(key, self.predefined_alarms):
            self.predefined_alarms[key] = valid_predefined[key]
            self.predefined_alarms[key][settings_key] = valid_predefined[key][
                settings_key
            ]
            if isinstance(value, dict) and keyisset(settings_key, value):
                self.predefined_alarms[key][settings_key] = valid_predefined[key][
                    settings_key
                ]
                for subkey, subvalue in value[settings_key].items():
                    self.predefined_alarms[key][settings_key][subkey] = subvalue

    def merge_alarm_settings(self, key, value, settings_key, valid_predefined):
        """
        Method to merge multiple services alarms definitions

        :param str key:
        :param dict value:
        :param str settings_key:
        :return:
        """
        for subkey, subvalue in value[settings_key].items():
            if isinstance(subvalue, (int, float)) and keyisset(
                subkey, self.predefined_alarms[key][settings_key]
            ):
                set_value = self.predefined_alarms[key][settings_key][subkey]
                new_value = subvalue
                LOG.warning(
                    f"Value for {key}.Settings.{subkey} override from {set_value} to {new_value}."
                )
                self.predefined_alarms[key]["Settings"][subkey] = new_value

    def set_merge_alarm_topics(self, key, value):
        topics = value["Topics"]
        set_topics = []
        if keyisset("Topics", self.predefined_alarms[key]):
            set_topics = self.predefined_alarms[key]["Topics"]
        else:
            self.predefined_alarms[key]["Topics"] = set_topics
        for topic in topics:
            if isinstance(topic, str) and topic not in [
                t for t in set_topics if isinstance(t, str)
            ]:
                set_topics.append(topic)
            elif (
                isinstance(topic, dict)
                and keyisset("x-sns", topic)
                and topic["x-sns"]
                not in [
                    t["x-sns"]
                    for t in set_topics
                    if isinstance(t, dict) and keyisset("x-sns", t)
                ]
            ):
                set_topics.append(topic)

    def assign_predefined_alerts(
        self, service_predefined, valid_predefined, settings_key
    ):
        for key, value in service_predefined.items():
            if not keyisset(key, self.predefined_alarms):
                self.define_default_alarm_settings(
                    key, value, settings_key, valid_predefined
                )
            elif (
                keyisset(key, self.predefined_alarms)
                and isinstance(value, dict)
                and keyisset(settings_key, value)
            ):
                self.merge_alarm_settings(key, value, settings_key, valid_predefined)
            if keyisset("Topics", value):
                self.set_merge_alarm_topics(key, value)

    def handle_alarms(self):
        """
        Method to define the alarms for the services.
        """
        valid_predefined = self.define_predefined_alarms()
        LOG.debug(self.logical_name, valid_predefined)
        if not valid_predefined:
            return
        alarm_key = "x-alarms"
        settings_key = "Settings"
        for service in self.services:
            if keyisset(alarm_key, service.definition) and keyisset(
                "Predefined", service.definition[alarm_key]
            ):
                service_predefined = service.definition[alarm_key]["Predefined"]
                self.validate_service_predefined_alarms(
                    valid_predefined, service_predefined
                )
                self.assign_predefined_alerts(
                    service_predefined, valid_predefined, settings_key
                )
                LOG.debug(self.predefined_alarms)

    def add_container_level_log_group(self, service, log_group_title, expiry):
        """
        Method to add a new log group for a specific container/service defined when awslogs-group has been set.

        :param service:
        :param str log_group_title:
        :param expiry:
        """
        if log_group_title not in self.template.resources:
            log_group = self.template.add_resource(
                LogGroup(
                    log_group_title,
                    LogGroupName=service.logging.Options["awslogs-group"],
                    RetentionInDays=expiry,
                )
            )
            policy = Policy(
                PolicyName=Sub(f"CloudWatchAccessFor${{{ecs_params.SERVICE_NAME_T}}}"),
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                            "Effect": "Allow",
                            "Action": [
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": GetAtt(log_group, "Arn"),
                        }
                    ],
                },
            )
            try:
                self.exec_role.Policies.append(policy)
            except AttributeError:
                setattr(self.exec_role, "Policies", [policy])
            service.logging.Options.update({"awslogs-group": Ref(log_group)})
        else:
            LOG.debug("LOG Group and policy already exist")

    def handle_logging(self):
        """
        Method to go over each service logging configuration and accordingly define the IAM permissions needed for
        the exec role
        """
        if not self.template:
            return
        for service in self.services:
            expiry = set_logging_expiry(service)
            log_group_title = f"{service.logical_name}LogGroup"
            if keyisset("awslogs-region", service.logging.Options) and not isinstance(
                service.logging.Options["awslogs-region"], Ref
            ):
                LOG.warning(
                    "When defining awslogs-region, Compose-X does not create the CW Log Group"
                )
                self.exec_role.Policies.append(
                    Policy(
                        PolicyName=Sub(
                            f"CloudWatchAccessFor${{{ecs_params.SERVICE_NAME_T}}}"
                        ),
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                                    "Effect": "Allow",
                                    "Action": [
                                        "logs:CreateLogStream",
                                        "logs:CreateLogGroup",
                                        "logs:PutLogEvents",
                                    ],
                                    "Resource": "*",
                                }
                            ],
                        },
                    )
                )
            elif keyisset("awslogs-group", service.logging.Options) and not isinstance(
                service.logging.Options["awslogs-group"], (Ref, Sub)
            ):
                self.add_container_level_log_group(service, log_group_title, expiry)
            else:
                service.logging.Options.update(
                    {"awslogs-group": Ref(ecs_params.LOG_GROUP_T)}
                )

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
            if (
                service.container_start_condition == "SUCCESS"
                or service.container_start_condition == "COMPLETE"
                or service.is_aws_sidecar
                or not service.is_essential
            ):
                service.container_definition.Essential = False
            else:
                service.container_definition.Essential = True

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
        if len(ordered_containers_config) == 1:
            LOG.debug("There is only one service, we need to ensure it is essential")
            ordered_containers_config[0][1].container_definition.Essential = True

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
            ("ManagedPolicyArns", list, None),
            ("Policies", list, add_policies),
            ("PermissionsBoundary", (str, Sub), handle_iam_boundary),
        ]
        iam_settings = [service.x_iam for service in self.services if service.x_iam]
        for setting in iam_settings:
            for key in valid_keys:
                self.sort_iam_settings(key, setting)

        self.set_secrets_access()

    def handle_permission_boundary(self, prop_key):
        if keyisset("PermissionsBoundary", self.iam) and self.template:
            if EXEC_ROLE_T in self.template.resources:
                add_role_boundaries(
                    self.template.resources[EXEC_ROLE_T], self.iam[prop_key]
                )
            if TASK_ROLE_T in self.template.resources:
                add_role_boundaries(
                    self.template.resources[TASK_ROLE_T], self.iam[prop_key]
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
                "ManagedPolicyArns",
                "ManagedPolicyArns",
                list,
                self.assign_iam_managed_policies,
            ),
            ("Policies", "Policies", list, self.assign_iam_policies),
            ("PermissionsBoundary", "PermissionsBoundary", (str, Sub), None),
        ]
        for prop in props:
            if keyisset(prop[0], self.iam) and isinstance(self.iam[prop[0]], prop[2]):
                if prop[0] == "PermissionsBoundary":
                    self.handle_permission_boundary(prop[0])
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
                LOG.warning(
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
            EphemeralStorage=If(
                USE_FARGATE_CON_T,
                EphemeralStorage(SizeInGiB=self.task_ephemeral_storage),
                Ref(AWS_NO_VALUE),
            )
            if 0 < self.task_ephemeral_storage >= 21
            else Ref(AWS_NO_VALUE),
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
        for service in self.services:
            service.container_definition.DockerLabels.update(
                {
                    "container_name": service.container_name,
                    "ecs_task_family": Ref(ecs_params.SERVICE_NAME),
                }
            )

    def apply_services_params(self):
        if not self.template:
            return
        for service in self.services:
            self.stack_parameters.update({service.image_param.title: service.image})
            if service.image_param.title not in self.template.parameters:
                self.template.add_parameter(service.image_param)

    def refresh_container_logging_definition(self):
        for service in self.services:
            c_def = service.container_definition
            logging_def = c_def.LogConfiguration
            logging_def.Options.update(self.task_logging_options)

    def init_task_definition(self):
        if self.template:
            add_service_roles(self)
        self.set_task_compute_parameter()
        self.set_task_definition()
        self.refresh_container_logging_definition()

    def update_family_subnets(self, settings):
        """
        Method to update the stack parameters

        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        network_names = list(self.service_config.network.networks.keys())
        for network in settings.networks:
            if network.name in network_names:
                self.stack_parameters.update(
                    {
                        APP_SUBNETS.title: Join(
                            ",",
                            FindInMap("Network", network.subnet_name, "Ids"),
                        )
                    }
                )
                LOG.info(
                    f"Set {network.subnet_name} as {APP_SUBNETS.title} for {self.name}"
                )

    def upload_services_env_files(self, settings):
        """
        Method to go over each service and if settings are to upload files to S3, will create objects and update the
        container definition for env_files accordingly.

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        if settings.no_upload:
            return
        elif settings.for_cfn_macro:
            LOG.warning("When running as a Macro, you cannot upload environment files.")
            return
        for service in self.services:
            env_files = []
            for env_file in service.env_files:
                with open(env_file, "r") as file_fd:
                    file_body = file_fd.read()
                object_name = path.basename(env_file)
                try:
                    upload_file(
                        body=file_body,
                        bucket_name=settings.bucket_name,
                        mime="text/plain",
                        prefix=f"{FILE_PREFIX}/env_files",
                        file_name=object_name,
                        settings=settings,
                    )
                    LOG.info(f"Successfully uploaded {env_file} to S3")
                except Exception:
                    LOG.error(f"Failed to upload env file {object_name}")
                    raise
                file_path = Sub(
                    f"arn:${{{AWS_PARTITION}}}:s3:::{settings.bucket_name}/{FILE_PREFIX}/env_files/{object_name}"
                )
                env_files.append(EnvironmentFile(Type="s3", Value=file_path))
            if not hasattr(service.container_definition, "EnvironmentFiles"):
                setattr(service.container_definition, "EnvironmentFiles", env_files)
            else:
                service.container_definition.EnvironmentFiles += env_files
            if "S3EnvFilesAccess" not in [
                policy.PolicyName
                for policy in self.exec_role.Policies
                if isinstance(policy.PolicyName, str)
            ]:
                self.exec_role.Policies.append(
                    Policy(
                        PolicyName="S3EnvFilesAccess",
                        PolicyDocument={
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Action": "s3:GetObject",
                                    "Effect": "Allow",
                                    "Resource": Sub(
                                        f"arn:${{{AWS_PARTITION}}}:s3:::{settings.bucket_name}/*"
                                    ),
                                }
                            ],
                        },
                    )
                )

    def set_repository_credentials(self, settings):
        """
        Method to go over each service and identify which ones have credentials to pull the Docker image from a private
        repository

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
        """
        for service in self.services:
            if not service.x_repo_credentials:
                continue
            if service.x_repo_credentials.startswith("arn:aws"):
                secret_arn = service.x_repo_credentials
            elif service.x_repo_credentials.startswith("secrets::"):
                secret_name = service.x_repo_credentials.split("::")[-1]
                secret_arn = identify_repo_credentials_secret(
                    settings, self, secret_name
                )
            else:
                raise ValueError(
                    "The secret for private repository must be either an ARN or the name of a secret defined in secrets"
                )
            setattr(
                service.container_definition,
                "RepositoryCredentials",
                RepositoryCredentials(CredentialsParameter=secret_arn),
            )
            self.exec_role.Policies.append(
                Policy(
                    PolicyName="AccessToRepoCredentialsSecret",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["secretsmanager:GetSecretValue"],
                                "Sid": "AccessToRepoCredentialsSecret",
                                "Resource": [secret_arn],
                            }
                        ],
                    },
                )
            )

    def set_services_mount_points(self):
        """
        Method to set the mount points to the Container Definition of the defined service
        """
        for service in self.services:
            mount_points = []
            if not hasattr(service.container_definition, "MountPoints"):
                setattr(service.container_definition, "MountPoints", mount_points)
            else:
                mount_points = getattr(service.container_definition, "MountPoints")
            for volume in service.volumes:
                mnt_point = MountPoint(
                    ContainerPath=volume["target"],
                    ReadOnly=volume["read_only"],
                    SourceVolume=volume["volume"].volume_name,
                )
                mount_points.append(mnt_point)

    def define_shared_volumes(self):
        """
        Method to create a list of shared volumes within the task family and set the volume to shared = True if not.

        :return: list of shared volumes within the task definition
        :rtype: list
        """
        family_task_volumes = []
        for service in self.services:
            for volume in service.volumes:
                if volume["volume"] and volume["volume"] not in family_task_volumes:
                    family_task_volumes.append(volume["volume"])
                else:
                    volume["volume"].is_shared = True
        return family_task_volumes

    def set_volumes(self):
        """
        Method to create the volumes definition to the Task Definition

        :return:
        """
        family_task_volumes = self.define_shared_volumes()
        family_definition_volumes = []
        if not hasattr(self.task_definition, "Volumes"):
            setattr(self.task_definition, "Volumes", family_definition_volumes)
        else:
            family_definition_volumes = getattr(self.task_definition, "Volumes")
        for volume in family_task_volumes:
            if volume.type == "volume" and volume.driver == "local":
                volume.cfn_volume = Volume(
                    Host=Ref(AWS_NO_VALUE),
                    Name=volume.volume_name,
                    DockerVolumeConfiguration=If(
                        USE_FARGATE_CON_T,
                        Ref(AWS_NO_VALUE),
                        DockerVolumeConfiguration(
                            Scope="task" if not volume.is_shared else "shared",
                            Autoprovision=Ref(AWS_NO_VALUE)
                            if not volume.is_shared
                            else True,
                        ),
                    ),
                )
            if volume.cfn_volume:
                family_definition_volumes.append(volume.cfn_volume)
        self.set_services_mount_points()

    def set_service_update_config(self):
        """
        Method to determine the update_config for the service. When a family has multiple containers, this applies
        to all tasks.
        """
        min_percents = [
            int(service.definition["x-aws-min_percent"])
            for service in self.services
            if keypresent("x-aws-min_percent", service.definition)
        ]
        max_percents = [
            int(service.definition["x-aws-max_percent"])
            for service in self.services
            if keypresent("x-aws-max_percent", service.definition)
        ]
        if min_percents:
            minis_sum = sum(min_percents)
            if not minis_sum:
                family_min_percent = 0
            else:
                family_min_percent = minis_sum / len(min_percents)
        else:
            family_min_percent = 100

        if max_percents:
            maxis_sum = sum(max_percents)
            if not maxis_sum:
                family_max_percent = 0
            else:
                family_max_percent = maxis_sum / len(max_percents)
        else:
            family_max_percent = 200
        rollback = True
        actions = [
            service.update_config["failure_action"] != "rollback"
            for service in self.services
            if service.update_config
            and keyisset("failure_action", service.update_config)
        ]
        if any(actions):
            rollback = False
        self.deployment_config.update(
            {
                "MinimumHealthyPercent": family_min_percent,
                "MaximumPercent": family_max_percent,
                "RollBack": rollback,
            }
        )

    def handle_prometheus(self):
        """
        Reviews services config
        :return:
        """
        from ecs_composex.ecs.ecs_prometheus import add_cw_agent_to_family

        insights_options = {
            "CollectForAppMesh": False,
            "CollectForJavaJmx": False,
            "CollectForNginx": False,
            "EnableTasksDiscovery": False,
            "EnableCWAgentDebug": False,
            "AutoAddNginxPrometheusExporter": False,
        }
        for service in self.services:
            if keyisset("x-prometheus", service.definition):
                prometheus_config = service.definition["x-prometheus"]
                if keyisset("ContainersInsights", prometheus_config):
                    config = service.definition["x-prometheus"]["ContainersInsights"]
                    for key in insights_options.keys():
                        if keyisset(key, config):
                            insights_options[key] = config[key]
                    if keyisset("CustomRules", config):
                        insights_options.update({"CustomRules": config["CustomRules"]})
        if any(insights_options.values()):
            add_cw_agent_to_family(self, **insights_options)

    def merge_capacity_providers(self):
        """
        Merge capacity providers set on the services of the task family if service is not sidecar
        """
        task_config = {}
        for svc in self.services:
            if not svc.capacity_provider_strategy or svc.is_aws_sidecar:
                continue
            for provider in svc.capacity_provider_strategy:
                if provider["CapacityProvider"] not in task_config.keys():
                    name = provider["CapacityProvider"]
                    task_config[name] = {
                        "Base": [],
                        "Weight": [],
                        "CapacityProvider": name,
                    }
                    task_config[name]["Base"].append(
                        set_else_none("Base", provider, alt_value=0)
                    )
                    task_config[name]["Weight"].append(
                        set_else_none("Weight", provider, alt_value=0)
                    )
        for provider in task_config.values():
            provider["Base"] = int(max(provider["Base"]))
            provider["Weight"] = int(max(provider["Weight"]))
        self.ecs_capacity_providers = list(task_config.values())
        if self.ecs_capacity_providers:
            self.launch_type = "CAPACITY_PROVIDERS"
            cfn_capacity_providers = [
                CapacityProviderStrategyItem(**props)
                for props in self.ecs_capacity_providers
            ]
            if isinstance(self.service_definition, EcsService):
                setattr(
                    self.service_definition,
                    "CapacityProviderStrategy",
                    cfn_capacity_providers,
                )

    def validate_capacity_providers(self, cluster_providers):
        """
        Validates that the defined ecs_capacity_providers are all available in the ECS Cluster Providers

        :param list[str] cluster_providers:
        :raises: ValueError if not all task family providers in the cluster providers
        :raises: TypeError if cluster_providers not a list
        """
        cap_names = [cap["CapacityProvider"] for cap in self.ecs_capacity_providers]
        if not isinstance(cluster_providers, list):
            raise TypeError("clusters_providers must be a list")
        if not self.ecs_capacity_providers:
            LOG.info(
                f"{self.name} - No capacity providers specified in task definition"
            )
            return True
        elif not cluster_providers:
            LOG.info(f"{self.name} - No capacity provider set for cluster")
            return True
        elif not all(provider in cluster_providers for provider in cap_names):
            raise ValueError(
                "Providers",
                cap_names,
                "not defined in ECS Cluster providers. Valid values are",
                cluster_providers,
            )

    def validate_compute_configuration_for_task(self, settings):
        """
        Function to perform a final validation of compute before rendering.
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        if settings.ecs_cluster_platform_override:
            self.launch_type = settings.ecs_cluster_platform_override
            if hasattr(
                self.service_definition, "CapacityProviderStrategy"
            ) and isinstance(self.service_definition.CapacityProviderStrategy, list):
                LOG.warning(
                    f"Due to Launch Type override to {settings.ecs_cluster_platform_override}"
                    ", ignoring CapacityProviders"
                )
                setattr(
                    self.service_definition,
                    "CapacityProviderStrategy",
                    Ref(AWS_NO_VALUE),
                )
                if self.stack:
                    self.stack.Parameters.update(
                        {ecs_params.LAUNCH_TYPE.title: self.launch_type}
                    )
        else:
            self.merge_capacity_providers()
            if (
                hasattr(self.service_definition, "CapacityProviderStrategy")
                and isinstance(self.service_definition.CapacityProviderStrategy, list)
                and self.stack
            ):
                self.stack.Parameters.update(
                    {ecs_params.LAUNCH_TYPE.title: "CAPACITY_PROVIDERS"}
                )
                LOG.info(
                    f"{self.name} - Updated {ecs_params.LAUNCH_TYPE.title} to CAPACITY_PROVIDERS"
                )
