#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to import the services defined in compose files and import / transform the settings into
Compose-X usable properties
"""

import re
import warnings
from copy import deepcopy
from os import path

try:
    import docker

    USE_DOCKER = True
except ImportError:
    USE_DOCKER = False
    warnings.warn(
        "Due to security issues not addressed by docker python, this is temporarily disabled.",
        DeprecationWarning,
    )
import requests
import urllib3
from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import AWS_NO_VALUE, AWS_REGION, If, NoValue, Ref, Sub
from troposphere.ecs import (
    ContainerDefinition,
    HealthCheck,
    KernelCapabilities,
    LinuxParameters,
    LogConfiguration,
    PortMapping,
    SystemControl,
    Tmpfs,
    Ulimit,
)

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, Parameter
from ecs_composex.compose.compose_secrets.services_helpers import map_secrets
from ecs_composex.compose.compose_services.docker_tools import (
    import_time_values_to_seconds,
    set_compute_resources,
    set_memory_to_mb,
)
from ecs_composex.compose.compose_services.helpers import (
    define_ingress_mappings,
    import_env_variables,
    validate_healthcheck,
)
from ecs_composex.compose.compose_volumes.services_helpers import map_volumes
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_conditions import (
    IPC_FROM_HOST_CON_T,
    USE_FARGATE_CON_T,
    USE_LINUX_OS_T,
    USE_WINDOWS_OS_T,
)


class ComposeService:
    """
    Class to represent a service

    :cvar str container_name: name of the container to use in definitions
    """

    main_key = "services"
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

        for setting in self.ecs_plugin_aws_keys:
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

        self.deploy_labels = {}
        self.x_configs = set_else_none("x-configs", self.definition)
        self.x_scaling = set_else_none("x-scaling", self.definition, None, False)
        self.x_network = set_else_none("x-network", self.definition, None, False)
        self.x_cloudmap = set_else_none("x-cloudmap", self.x_network, None, False)
        self.eip_auto_assign = set_else_none("AssignPublicIp", self.x_network, False)
        self.x_ray = set_else_none(
            "x-xray",
            self.definition,
            set_else_none("x-ray", self.definition, False, True),
            True,
        )
        self.x_iam = set_else_none("x-iam", self.definition)
        self.x_logging = {"RetentionInDays": 14}
        self.x_repo_credentials = None
        self.ipc = set_else_none("ipc", self.definition)
        self.import_x_aws_settings()
        self.networks = set_else_none("networks", self.definition, {})
        self.replicas = 1
        self.container = None
        self.volumes = []
        self.logging = {}
        self.secrets = []
        self.env_files = []
        self.tmpfses = []
        self.ephemeral_storage = 0
        self.family_hostname = None
        self.x_ecs = set_else_none("x-ecs", self.definition, {})
        self.user = None
        self.group = None
        self.ulimits = set_else_none("ulimits", self.definition, [])
        self.user_group = None
        self.code_profiler = None
        self.set_env_files()
        self.environment = set_else_none("environment", self.definition, None, False)
        self.cfn_environment = (
            import_env_variables(self.environment) if self.environment else NoValue
        )
        self.depends_on = set_else_none("depends_on", self.definition, [], False)
        self.command = (
            definition["command"] if keyisset("command", definition) else NoValue
        )
        if not keyisset("image", self.definition):
            raise KeyError("You must specify the image to use for", self.name)
        self.image = self.definition["image"]
        self.image_digest = None
        self.image_param = Parameter(
            f"{self.logical_name}ImageUrl", Default=self.image, Type="String"
        )
        self.ecr_config = set_else_none("x-ecr", self.definition, None)
        self.launch_type = None
        self.container_start_condition = "START"

        self.mem_alloc = None
        self.mem_resa = None
        self.cpu_amount = None
        self.families = []
        self.my_family = None
        self.is_aws_sidecar = False
        self._is_essential = True
        self.container_definition = None

        self.ecs_healthcheck = NoValue
        self.healthcheck = set_else_none("healthcheck", self.definition, None)
        self.deploy = set_else_none("deploy", self.definition, None)
        self.set_service_deploy()
        self.ports = set_else_none("ports", self.definition, [])
        self.expose_ports = set_else_none("expose", self.definition, [])
        self.ingress_mappings = define_ingress_mappings(self.ports)

        self.update_config = {}
        self.working_dir = set_else_none(
            "working_dir", self.definition, alt_value=NoValue
        )
        self.x_ecs = set_else_none("x-ecs", self.definition, None)
        self.capacity_provider_strategy = set_else_none(
            "CapacityProviderStrategy", self.x_ecs, None
        )
        self.runtime_architecture = set_else_none("CpuArchitecture", self.x_ecs, None)
        self.runtime_os_family = set_else_none(
            "OperatingSystemFamily", self.x_ecs, None
        )

        self.set_ecs_healthcheck()
        self.define_logging()

        self.set_user_group()
        map_volumes(self, volumes)
        map_secrets(self, secrets)
        self.define_families()
        self.set_container_definition()
        self.set_update_networks()

    def __repr__(self):
        return self.name

    @property
    def is_essential(self):
        return self._is_essential

    @is_essential.setter
    def is_essential(self, value: bool):
        self._is_essential = value
        if self.container_definition:
            setattr(self.container_definition, "Essential", self._is_essential)

    def retrieve_image_digest(self):
        """
        Retrieves the docker images digest from the repository to use instead of the image tag.
        """
        valid_media_types = [
            "application/vnd.docker.distribution.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.docker.distribution.manifest.v1+prettyjws",
            "application/vnd.docker.distribution.manifest.list.v2+json",
        ]
        if not USE_DOCKER:
            return
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

    def handle_expose_ports(self, aws_vpc_mappings):
        """
        Import the expose ports to AWS VPC Mappings

        :param list[troposphere.ecs.PortMapping] aws_vpc_mappings: List of ECS Port Mappings defined from ports[]
        """
        expose_port_re = re.compile(r"^(?P<target>\d{1,5})(?=/(?P<protocol>udp|tcp))")
        for expose_port in self.expose_ports:
            if isinstance(expose_port, str):
                parts = expose_port_re.match(expose_port)
                if not parts:
                    raise ValueError(
                        "Expose port value is invalid. Must match",
                        expose_port_re.pattern,
                    )
                port = int(parts.group("target"))
                protocol = parts.group("protocol") or "tcp"
            elif isinstance(expose_port, int):
                port = expose_port
                protocol = "tcp"
            else:
                raise TypeError(
                    expose_port, "is", type(expose_port), "expected one of", (str, int)
                )
            if port not in [p.ContainerPort for p in aws_vpc_mappings]:
                aws_vpc_mappings.append(
                    PortMapping(
                        HostPort=NoValue,
                        ContainerPort=port,
                        Protocol=protocol.lower(),
                    )
                )
            else:
                LOG.debug(
                    f"{self.name} - Port {port} was already defined as ``ports``."
                    " In awsvpc mode the Container Ports must be unique."
                    f" Skipping {self.name}.expose.{expose_port}"
                )

    def define_port_mappings(self) -> list:
        """
        Define the list of port mappings to use for either AWS VPC deployments or else (bridge etc).
        Not in use atm as AWS VPC is made mandatory
        """
        service_port_mappings = (
            getattr(self.container_definition, "PortMappings")
            if self.container_definition
            else []
        )
        for protocol, mappings in self.ingress_mappings.items():
            for target_port, published_ports in mappings.items():
                if published_ports:
                    for port in published_ports:
                        service_port_mappings.append(
                            PortMapping(
                                ContainerPort=target_port,
                                HostPort=If(USE_FARGATE_CON_T, NoValue, port),
                                Protocol=protocol.lower(),
                            )
                        )
                else:
                    service_port_mappings.append(
                        PortMapping(
                            ContainerPort=target_port,
                            HostPort=NoValue,
                            Protocol=protocol.lower(),
                        )
                    )
            self.handle_expose_ports(service_port_mappings)
        return service_port_mappings

    def import_docker_labels(self):
        """
        Import the Docker labels if defined
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
        self.define_compose_logging()
        self.container_definition = ContainerDefinition(
            Image=Ref(self.image_param),
            Name=self.name,
            Cpu=self.cpu_amount if self.cpu_amount else NoValue,
            Memory=self.mem_alloc if self.mem_alloc else NoValue,
            MemoryReservation=self.mem_resa if self.mem_resa else NoValue,
            PortMappings=[],
            Environment=self.cfn_environment,
            LogConfiguration=self.logging,
            Command=self.command,
            HealthCheck=self.ecs_healthcheck,
            DependsOn=NoValue,
            Essential=self.is_essential,
            Secrets=secrets,
            Ulimits=If(USE_WINDOWS_OS_T, NoValue, self.define_ulimits())
            if self.ulimits
            else NoValue,
            LinuxParameters=If(
                USE_LINUX_OS_T,
                LinuxParameters(
                    Capabilities=self.define_kernel_options(),
                    SharedMemorySize=self.define_shm_size(),
                    Tmpfs=self.define_tmpfs(),
                ),
                NoValue,
            ),
            Privileged=If(
                USE_FARGATE_CON_T,
                NoValue,
                If(USE_WINDOWS_OS_T, NoValue, keyisset("Privileged", self.definition)),
            ),
            WorkingDirectory=self.working_dir,
            DockerLabels=self.import_docker_labels(),
            ReadonlyRootFilesystem=If(
                USE_WINDOWS_OS_T, NoValue, keyisset("read_only", self.definition)
            ),
            SystemControls=self.define_sysctls(),
            User=If(USE_WINDOWS_OS_T, NoValue, self.user_group)
            if self.user_group
            else NoValue,
        )

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
        if logging_def["driver"] not in valid_drivers:
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
                    "awslogs-endpoint", options_def, alt_value=NoValue
                ),
                "awslogs-datetime-format": set_else_none(
                    "awslogs-datetime-format",
                    options_def,
                    alt_value=NoValue,
                ),
                "awslogs-multiline-pattern": set_else_none(
                    "awslogs-multiline-pattern",
                    options_def,
                    alt_value=NoValue,
                ),
                "mode": set_else_none("mode", options_def, alt_value=Ref(AWS_NO_VALUE)),
                "max-buffer-size": set_else_none(
                    "max-buffer-size", options_def, alt_value=NoValue
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
            return NoValue
        elif keyisset(tmpfs_key, self.definition):
            if isinstance(self.definition[tmpfs_key], str):
                self.tmpfses.append(
                    {"ContainerPath": self.definition[tmpfs_key], "Size": 0}
                )
            elif isinstance(self.definition[tmpfs_key], list):
                for container_path in self.definition[tmpfs_key]:
                    self.tmpfses.append({"ContainerPath": container_path, "Size": 0})
        rendered_fs = [Tmpfs(**args) for args in self.tmpfses]
        return If(USE_FARGATE_CON_T, NoValue, rendered_fs)

    def define_sysctls(self):
        """
        Method to define the SystemControls
        """
        sysctls_key = "sysctls"
        if not keyisset(sysctls_key, self.definition):
            return NoValue
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
        return If(
            IPC_FROM_HOST_CON_T, NoValue, If(USE_FARGATE_CON_T, NoValue, controls)
        )

    def define_shm_size(self):
        """
        Method to import and determine SHM SIZE
        """
        if not keyisset("shm_size", self.definition):
            return NoValue
        memory_value = set_memory_to_mb(self.definition["shm_size"])
        return If(USE_FARGATE_CON_T, NoValue, memory_value)

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
        Set the drop kernel capacities

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
                        f"{self.name} - Linux kernel capacity {capacity} is not supported in ECS or simply not valid"
                    )
                if capacity in all_adds or capacity in cap_adds:
                    raise KeyError(
                        f"{self.name} - Capacity {capacity} already detected in cap_add. "
                        "You cannot both add and remove the capacity"
                    )
                if capacity in fargate:
                    cap_adds.append(capacity)
                else:
                    all_drops.append(capacity)

    def define_kernel_options(self):
        """
        Define and return the kernel option settings for cap_add and cap_drop
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
            return NoValue

        self.set_add_capacities(add_key, valid, cap_adds, all_adds, fargate)
        self.set_drop_capacities(
            drop_key, valid, cap_adds, all_adds, all_drops, fargate
        )
        kwargs = {
            "Add": cap_adds or NoValue,
            "Drop": cap_drops or NoValue,
        }
        if all_adds:
            cap_adds.append(If(USE_FARGATE_CON_T, NoValue, all_adds))
        if all_drops:
            cap_drops.append(If(USE_FARGATE_CON_T, NoValue, all_drops))
        return KernelCapabilities(**kwargs)

    def define_ulimits(self):
        """
        Set the ulimits
        """
        if not self.ulimits:
            return NoValue
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
        for limit_name, limit_value in self.ulimits.items():
            if limit_name not in allowed:
                raise KeyError(
                    f"{self.name} - ulimit property {limit_name} is not supported by ECS. Valid ones are",
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
                raise TypeError(f"{self.name} - ulimit is not of the proper definition")
            if limit_name not in fargate_supported:
                rendered_limits.append(If(USE_FARGATE_CON_T, NoValue, ulimit))
            else:
                rendered_limits.append(ulimit)
        if rendered_limits:
            return rendered_limits
        return NoValue

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
            valid_pattern = re.compile(r"^\d{1,5}$|(^\d{1,5}):(\d{1,5})$")
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

    def set_update_networks(self):
        """
        Sets / Assigns tne network to use based services.networks
        """
        if isinstance(self.networks, list):
            new_definition = {}
            for name in self.networks:
                new_definition[name] = {}
            self.networks = new_definition

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

    def is_in_family(self, family_name):
        """
        Method to check whether this service is part of a given family

        :param str family_name:
        :return: True/False
        :rtype: bool
        """
        return family_name in self.families

    def set_ecs_healthcheck(self):
        """
        Function to set healtcheck configuration
        :return:
        """
        if not self.healthcheck:
            self.ecs_healthcheck = NoValue
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

    def set_service_labels(self, deployments):
        labels = "labels"
        if not keyisset(labels, deployments):
            return
        self.deploy_labels = deployments[labels]
        custom_keys = re.compile(r"^ecs\.[\S]+$")
        keys = [name for name in self.deploy_labels.keys()]
        for key in keys:
            if custom_keys.match(key):
                del self.deploy_labels[key]

    def set_family_hostname(self, deployments):
        """
        Override family_hostname based on label

        :param dict deployments:
        """
        labels = "labels"
        hostname = "ecs.task.family.hostname"
        if not keyisset(labels, deployments):
            return
        labels = deployments[labels]
        if not keyisset(hostname, labels):
            return
        self.family_hostname = labels[hostname]

    def set_service_deploy(self):
        """
        Function to setup the service configuration from the deploy section of the service in compose file.
        """
        deploy = "deploy"
        if not keyisset("deploy", self.definition):
            return
        self.define_compute_platform(self.definition[deploy])
        set_compute_resources(self, self.definition[deploy])
        self.set_replicas(self.definition[deploy])
        self.define_start_condition(self.definition[deploy])
        self.define_essential(self.definition[deploy])
        self.set_update_config(self.definition[deploy])
        self.define_ephemeral_storage_condition(self.definition[deploy])
        self.set_family_hostname(self.definition[deploy])
        # self.set_service_labels(self.definition[deploy])
