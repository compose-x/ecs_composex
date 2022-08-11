#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to import the services defined in compose files and import / transform the settings into
Compose-X usable properties
"""

from __future__ import annotations

import re
import shlex
from copy import deepcopy
from os import path
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import AWSHelperFn, If, NoValue, Ref, Sub
from troposphere.ecs import (
    ContainerDefinition,
    HealthCheck,
    KernelCapabilities,
    LinuxParameters,
    PortMapping,
    SystemControl,
    Tmpfs,
    Ulimit,
)

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, Parameter
from ecs_composex.common.logging import LOG
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
from ecs_composex.ecs.ecs_conditions import (
    IPC_FROM_HOST_CON_T,
    USE_FARGATE_CON_T,
    USE_WINDOWS_OS_T,
)

from ...common.troposphere_tools import add_parameters
from .helpers import extend_container_envvars
from .service_image import ServiceImage


class ComposeService:
    """
    Class to represent a docker-compose singleton service

    :ivar str container_name: name of the container to use in definitions
    :ivar ecs_composex.compose.compose_services.service_logging.ServiceLogging logging:
    :ivar ServiceImage image:
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

    def __init__(
        self,
        name,
        definition,
        volumes=None,
        secrets=None,
        image_param: Parameter = None,
    ):

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
        self._definition = deepcopy(definition)
        self.original_definition = definition
        self.name = name
        self.container_definition = None
        self.container_name = name
        self.service_name = Sub(f"${{{ROOT_STACK_NAME.title}}}-{self.name}")

        self.x_scaling = set_else_none("x-scaling", self.definition, None, False)
        self.x_network = set_else_none("x-network", self.definition, None, False)
        self.x_cloudmap = set_else_none("x-cloudmap", self.x_network, None, False)
        self.x_ecs = set_else_none("x-ecs", self.definition, {})
        self.ecr_config = set_else_none("x-ecr", self.definition, None)
        self.x_ecr = set_else_none("x-ecr", self.definition, {})
        self.eip_auto_assign = set_else_none("AssignPublicIp", self.x_network, False)
        self.x_ray = set_else_none(
            "x-xray",
            self.definition,
            set_else_none("x-ray", self.definition, False, True),
            True,
        )

        self.x_repo_credentials = None
        self.ipc = set_else_none("ipc", self.definition)
        self.import_x_aws_settings()
        self.volumes = []
        self.logging = None
        self.secrets = []
        self.tmpfses = []
        self.user = None
        self.group = None
        self.user_group = None
        self.code_profiler = None

        self.environment = set_else_none("environment", self.definition, None, False)
        self.cfn_environment = (
            import_env_variables(self.environment) if self.environment else NoValue
        )
        self.depends_on = set_else_none("depends_on", self.definition, [], False)

        if not keyisset("image", self.definition):
            raise KeyError("You must specify the image to use for", self.name)

        if not image_param:
            self.image = ServiceImage(self)
        else:
            self.image = ServiceImage(self, image_param)

        self._mem_alloc = None
        self._mem_resa = None
        self._cpu_amount = None
        self.__family = None
        self.is_aws_sidecar = False

        self.deploy = set_else_none("deploy", self.definition, None)
        self.deploy_labels = set_else_none("labels", self.deploy, alt_value={})
        if self.deploy:
            set_compute_resources(self, self.deploy)

        self.ports = set_else_none("ports", self.definition, [])
        self.expose_ports = set_else_none("expose", self.definition, [])
        self.ingress_mappings = define_ingress_mappings(self.ports)

        self.set_user_group()
        map_volumes(self, volumes)
        map_secrets(self, secrets)
        self.set_container_definition()
        self.links = set_else_none("links", definition)
        self.family_links: list = []

    def __repr__(self):
        return self.name

    @property
    def definition(self):
        return self._definition

    @property
    def compose_x_arn(self) -> str:
        if self.family:
            return f"{self.family.name}::{self.name}"
        else:
            return self.name

    @property
    def family(self) -> ComposeFamily:
        return self.__family if self.__family else None

    @family.setter
    def family(self, family: ComposeFamily):
        self.__family = family
        if family.template:
            add_parameters(family.template, [self.image.image_param])
        if (
            family.stack
            and isinstance(self.image, ServiceImage)
            and isinstance(self.image.image, str)
        ):
            family.stack.Parameters.update(
                {self.image.image_param.title: self.image.image_uri}
            )

    @property
    def ecs_user(self) -> Union[str, AWSHelperFn]:
        __user = set_else_none("user", self.definition, alt_value=None)
        if not __user:
            return NoValue
        return str(__user)

    @property
    def deploy_labels(self):
        return set_else_none("labels", self.deploy, alt_value={})

    @deploy_labels.setter
    def deploy_labels(self, value: dict):
        if not self.deploy:
            self.deploy: dict = {"labels": value}
        if keypresent("labels", self.deploy) and not keyisset("labels", self.deploy):
            self.deploy["labels"]: dict = value
        elif keyisset("labels", self.deploy):
            self.deploy.update(value)

    @property
    def networks(self):
        _networks = set_else_none("networks", self.definition, alt_value={})
        if isinstance(_networks, list):
            new_definition = {}
            for name in _networks:
                new_definition[name] = {}
            return new_definition
        elif isinstance(_networks, dict):
            return _networks
        else:
            raise TypeError(
                self.name,
                "networks is of type",
                type(_networks),
                "must be one of",
                (dict, list),
            )

    @networks.setter
    def networks(self, value):
        if not isinstance(value, (list, dict)) or not issubclass(
            type(value), AWSHelperFn
        ):
            raise TypeError(
                self.name,
                "networks is of type",
                type(value),
                "must be one of",
                (dict, list),
                "or",
                AWSHelperFn,
            )
        if isinstance(value, list):
            new_definition = {}
            for name in value:
                new_definition[name] = {}
            value = new_definition
        self.definition["networks"]: dict = value

    @property
    def logical_name(self) -> str:
        return NONALPHANUM.sub("", self.name)

    @property
    def resources(self):
        return set_else_none("resources", self.deploy, alt_value={})

    @property
    def cpu_amount(self) -> Union[int, Ref]:
        if not self._cpu_amount or self.container_start_condition in [
            "SUCCESS",
            "COMPLETE",
        ]:
            return NoValue
        alloc = "limits"
        resa = "reservations"
        resource = "cpus"
        _set_limit = float(
            set_else_none(
                resource,
                set_else_none(alloc, self.resources, alt_value={}),
                alt_value=0,
            )
        )
        _set_resa = float(
            set_else_none(
                resource,
                set_else_none(resa, self.resources, alt_value={}),
                alt_value=0,
            )
        )
        to_set = float(max([_set_limit, _set_resa]))
        if to_set:
            return int(float(to_set * 1024))
        return NoValue

    @cpu_amount.setter
    def cpu_amount(self, value: Union[int, AWSHelperFn, None]):
        self._cpu_amount = value

    @property
    def memory_limit(self):
        if self.container_start_condition in [
            "SUCCESS",
            "COMPLETE",
        ]:
            return NoValue
        resource = "memory"
        str_value = set_else_none(
            resource, set_else_none("limits", self.resources, alt_value=None)
        )
        if not str_value:
            return NoValue
        return set_memory_to_mb(str_value)

    @property
    def memory_reservations(self):
        if self.container_start_condition in [
            "SUCCESS",
            "COMPLETE",
        ]:
            return NoValue
        resource = "memory"
        str_value = set_else_none(
            resource, set_else_none("reservations", self.resources, alt_value=None)
        )
        if not str_value:
            return NoValue
        return set_memory_to_mb(str_value)

    @property
    def command(self):
        _command = set_else_none("command", self.definition, alt_value=NoValue)
        if isinstance(_command, str):
            return shlex.split(_command)
        else:
            return _command

    @command.setter
    def command(self, new_command):
        self.definition.update({"command": new_command})
        if self.container_definition:
            setattr(self.container_definition, "Command", new_command)

    @property
    def runtime_architecture(self):
        return set_else_none("CpuArchitecture", self.x_ecs, None)

    @property
    def runtime_os_family(self):
        return set_else_none("OperatingSystemFamily", self.x_ecs, None)

    @property
    def capacity_provider_strategy(self):
        return set_else_none("CapacityProviderStrategy", self.x_ecs, None)

    @property
    def replicas(self):
        return int(set_else_none("replicas", self.deploy, alt_value=1))

    @replicas.setter
    def replicas(self, value: int):
        if not isinstance(value, int):
            raise ValueError(self.name, "replicas must be an integer")
        if self.deploy:
            self.deploy["replicas"] = value
        else:
            self.deploy = {"replicas": value}

    @property
    def working_dir(self):
        return set_else_none("working_dir", self.definition, alt_value=NoValue)

    @property
    def is_essential(self) -> bool:
        """
        In order of absolutes
        * If only 1 container in service, it must be essential
        * If user defined value (bool) and start condition is not SUCCESS or COMPLETE, then user defined
        * If not user defined value (None) and start condition is SUCCESS or COMPLETE, then it cannot be essential,
          as it is expected to shutdown
        """
        _tmp = True
        if self.family and len(self.family.services) == 1:
            _tmp = True
        elif self.user_define_essential and not (
            self.container_start_condition == "SUCCESS"
            or self.container_definition == "COMPLETE"
        ):
            _tmp = self.user_define_essential
        elif (
            self.container_start_condition == "SUCCESS"
            or self.container_definition == "COMPLETE"
        ):
            _tmp = False
        self.is_essential = _tmp
        if self.container_definition and hasattr(
            self.container_definition, "Essential"
        ):
            return self.container_definition.Essential
        else:
            return _tmp

    @is_essential.setter
    def is_essential(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(
                self.name,
                "is_essential must be one of",
                (bool, Ref),
                "got",
                type(value),
            )
        if self.container_definition:
            setattr(self.container_definition, "Essential", value)

    @property
    def user_define_essential(self) -> Union[None, bool]:
        """
        Allows user to override whether a container is essential or not.
        By default, in absence of the label, service is considered essential as it might
        be the only one in the family
        """
        essential_key = "ecs.essential"
        _defined_essential = set_else_none(
            essential_key, self.deploy_labels, alt_value=None
        )
        if _defined_essential is None:
            return None
        positive_values = [True, "yes", "True"]
        negative_values = [False, "no", "False"]
        if (
            _defined_essential not in positive_values
            or _defined_essential not in negative_values
        ):
            raise ValueError(
                "The values allowed for",
                essential_key,
                "are",
                positive_values,
                negative_values,
                "Got",
                _defined_essential,
            )
        if _defined_essential in negative_values:
            return False
        return True

    @property
    def container_start_condition(self) -> str:
        if (
            isinstance(self.ecs_healthcheck, HealthCheck)
            and self.ecs_healthcheck != NoValue
        ):
            return "HEALTHY"
        depends_key = "ecs.depends.condition"

        return set_else_none(
            depends_key,
            self.deploy_labels,
            alt_value="START",
        )

    @container_start_condition.setter
    def container_start_condition(self, value):
        depends_key = "ecs.depends.condition"
        valid_conditions = ["START", "COMPLETE", "SUCCESS", "HEALTHY"]
        if value not in valid_conditions:
            raise ValueError(
                self.name,
                depends_key,
                "is set to ",
                value,
                "must be one of",
                valid_conditions,
            )
        if self.deploy:
            if keyisset("labels", self.deploy):
                self.deploy["labels"][depends_key] = value
            else:
                self.deploy["labels"]: dict = {depends_key: value}
        else:
            self.deploy: dict = {"labels": {depends_key: value}}

    @property
    def ephemeral_storage(self):
        storage_key = "ecs.ephemeral.storage"
        storage_value = set_else_none(
            storage_key, set_else_none("labels", self.deploy, alt_value={}), alt_value=0
        )
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
        if ephemeral_storage <= 21:
            return 0

        elif ephemeral_storage > 200:
            return 200
        else:
            LOG.info(f"{self.name} - {storage_key} set to {ephemeral_storage}")
            return int(ephemeral_storage)

    @property
    def launch_type(self) -> Union[str, None]:
        compute_key = "ecs.compute.platform"
        return set_else_none(
            compute_key,
            set_else_none("labels", self.deploy, alt_value={}),
            alt_value=None,
        )

    @launch_type.setter
    def launch_type(self, value: str):
        compute_key = "ecs.compute.platform"
        valid = ["EC2", "FARGATE", "EXTERNAL"]
        if value not in valid:
            raise ValueError(
                self.name, compute_key, value, "is invalid. Must be one of", valid
            )
        if self.deploy:
            if keyisset("labels", self.deploy):
                self.deploy["labels"].update({compute_key: value})
            else:
                self.deploy["labels"] = {compute_key: value}
        else:
            self.deploy = {"labels": {compute_key: value}}

    @property
    def healthcheck(self):
        return set_else_none("healthcheck", self.definition, alt_value={})

    @property
    def ecs_healthcheck(self) -> Union[HealthCheck, AWSHelperFn]:
        """
        If HealthCheck already set ContainerDefinition and value is "None" but service.healtheck defined,
        define HealthCheck() from service.healthcheck.
        Elif already defined and not "None", return current value
        """
        __current = None
        if self.container_definition and hasattr(
            self.container_definition, "HealthCheck"
        ):
            __current = getattr(self.container_definition, "HealthCheck")
        if (
            (__current is None or __current == NoValue)
            and self.healthcheck
            and not self.container_definition
        ):
            if keyisset("disable", self.healthcheck):
                return NoValue
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
                _mapping = attr_mappings[key]
                ecs_key = _mapping[0]
                if _mapping[1] and callable(_mapping[1]):
                    params[ecs_key] = _mapping[1](value)
                else:
                    params[ecs_key] = value
            if isinstance(params["Command"], str):
                params["Command"] = ["CMD-SHELL", params["Command"]]
            return HealthCheck(**params)
        elif isinstance(__current, HealthCheck) or issubclass(
            type(__current), AWSHelperFn
        ):
            return __current
        return NoValue

    @property
    def family_hostname(self) -> str:
        hostname = "ecs.task.family.hostname"
        return set_else_none(
            hostname, set_else_none("labels", self.deploy, alt_value={}), alt_value=None
        )

    @property
    def update_config(self):
        _config = set_else_none("update_config", self.deploy, alt_value={})
        if not isinstance(_config, dict):
            raise TypeError(
                "The deploy.update_config must be a dict/map. Got",
                _config,
                type(_config),
            )
        return _config

    @property
    def families(self):
        ecs_task_family = "ecs.task.family"
        __families = set_else_none(ecs_task_family, self.deploy_labels)
        if __families is None:
            return [self.name]
        if not isinstance(__families, str):
            raise TypeError(
                ecs_task_family, "must be", str, "got", __families, type(__families)
            )
        return __families.split(r",")

    @property
    def tmpfs(self):
        """
        Method to define the tmpfs settings
        """
        tmpfs_key = "tmpfs"
        tmpfses = set_else_none(tmpfs_key, self.definition, alt_value=[])
        if not tmpfses:
            return NoValue
        if isinstance(self.definition[tmpfs_key], str):
            self.tmpfses.append(
                {"ContainerPath": self.definition[tmpfs_key], "Size": 0}
            )
        elif isinstance(self.definition[tmpfs_key], list):
            for container_path in self.definition[tmpfs_key]:
                self.tmpfses.append({"ContainerPath": container_path, "Size": 0})
        rendered_fs = [Tmpfs(**args) for args in self.tmpfses]
        return If(USE_FARGATE_CON_T, NoValue, rendered_fs)

    @property
    def sysctls(self):
        """
        Method to define the SystemControls
        """
        sysctls_key = "sysctls"
        __sysctls = set_else_none(sysctls_key, self.definition, alt_value={})
        if not __sysctls:
            return NoValue
        def_dict = {}
        if isinstance(__sysctls, list):
            for prop in __sysctls:
                splits = prop.split(r"=")
                if not splits or len(splits) != 2:
                    raise ValueError(f"Property define {prop} is not valid.")
                def_dict[splits[0]] = splits[1]
        elif isinstance(__sysctls, dict):
            def_dict = __sysctls
        controls = []
        for name, value in def_dict.items():
            controls.append(SystemControl(Namespace=name, Value=str(value)))
        return If(
            IPC_FROM_HOST_CON_T, NoValue, If(USE_FARGATE_CON_T, NoValue, controls)
        )

    @property
    def shm_size(self):
        """
        Method to import and determine SHM SIZE
        """
        __shm_size = set_else_none("shm_size", self.definition)
        if not __shm_size:
            return NoValue
        if not isinstance(__shm_size, (int, str, float)):
            raise TypeError(self.name)
        memory_value = set_memory_to_mb(__shm_size)
        return If(USE_FARGATE_CON_T, NoValue, memory_value)

    @property
    def kernel_properties(self) -> KernelCapabilities:
        from .kernel_options_helpers import define_kernel_options

        return define_kernel_options(self)

    @property
    def ulimits(self) -> Union[list, Ref]:
        """
        Set the ulimits
        """
        _ulimits = set_else_none("ulimits", self.definition, alt_value={})
        if not _ulimits:
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
        for limit_name, limit_value in _ulimits.items():
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
            elif isinstance(limit_value, dict):
                if keyisset("soft", limit_value) and keyisset("hard", limit_value):
                    ulimit = Ulimit(
                        SoftLimit=int(limit_value["soft"]),
                        HardLimit=int(limit_value["hard"]),
                        Name=limit_name,
                    )
                else:
                    raise KeyError(
                        f"Missing hard or soft properties for ulimit {limit_name}"
                    )
            else:
                raise TypeError(f"{self.name} - ulimit is not of the proper definition")
            if limit_name not in fargate_supported:
                rendered_limits.append(If(USE_FARGATE_CON_T, NoValue, ulimit))
            else:
                rendered_limits.append(ulimit)

        return rendered_limits if rendered_limits else NoValue

    @property
    def x_iam(self) -> dict:
        __iam = set_else_none(
            "x-iam",
            self.definition,
            alt_value={
                "ManagedPolicyArns": [],
                "Policies": [],
                "PermissionsBoundary": None,
            },
        )
        if keyisset("x-aws-policies", self.definition):
            __iam["ManagedPolicyArns"] += self.definition["x-aws-policies"]
        if keyisset("x-aws-role", self.definition):
            __iam["Policies"].append(
                {
                    "PolicyName": "ImportedFromXAWSRole",
                    "PolicyDocument": self.definition["x-aws-role"],
                }
            )
        return __iam

    @property
    def env_files(self) -> list:
        """
        Method to list all the env files and check the files are found and available.
        """
        env_file_key = "env_file"
        _env_files = set_else_none(env_file_key, self.definition)
        if not _env_files:
            return []
        if not isinstance(_env_files, (str, list)):
            raise TypeError(
                self.name,
                env_file_key,
                "must be one of",
                (str, list),
                "Got",
                _env_files,
                type(_env_files),
            )
        env_files = []
        if isinstance(self.definition[env_file_key], str):
            env_files = [_env_files]
        for file_path in _env_files:
            if not isinstance(file_path, str):
                raise TypeError(
                    "Files in the env_file is supposed to be a list of paths to files (str). Got",
                    type(file_path),
                )
            if not path.exists(path.abspath(file_path)):
                raise FileNotFoundError("No file found at", path.abspath(file_path))
            env_files.append(path.abspath(file_path))
        return env_files

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
        if self.container_definition:
            service_port_mappings = getattr(self.container_definition, "PortMappings")
        else:
            return []
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
        self.container_definition = ContainerDefinition(
            Image=Ref(self.image.image_param),
            Name=self.name,
            Cpu=self.cpu_amount,
            Memory=self.memory_limit,
            MemoryReservation=self.memory_reservations,
            PortMappings=[],
            Environment=self.cfn_environment,
            LogConfiguration=NoValue,
            Command=self.command,
            HealthCheck=self.ecs_healthcheck,
            DependsOn=NoValue,
            Essential=self.is_essential,
            Secrets=secrets,
            Ulimits=self.ulimits,
            LinuxParameters=If(
                USE_WINDOWS_OS_T,
                NoValue,
                LinuxParameters(
                    Capabilities=self.kernel_properties,
                    SharedMemorySize=self.shm_size,
                    Tmpfs=self.tmpfs,
                ),
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
            SystemControls=self.sysctls,
            User=If(USE_WINDOWS_OS_T, NoValue, self.ecs_user)
            if self.ecs_user != NoValue
            else self.ecs_user,
        )

        _to_add = [secret.env_var for secret in self.secrets]
        extend_container_envvars(self.container_definition, _to_add)

    def set_user_group(self):
        """
        Method to assign the user / group IDs for the container
        """
        user_value = set_else_none("user", self.definition, alt_value=None)
        if isinstance(user_value, int):
            self.user = str(user_value)
            self.group = self.user
        elif isinstance(user_value, str):
            valid_pattern = re.compile(
                r"(^\d{1,5}$|(?P<user>^\d{1,5}):(?P<group>\d{1,5})$)"
            )
            groups = valid_pattern.match(user_value)
            if not groups:
                raise ValueError("when using user:group, use the UID instead of name")
            if groups.group("user") and groups.group("group"):
                self.user = str(groups.group("user"))
                self.group = str(groups.group("group"))
            else:
                self.user = groups.groups()[0]
                self.group = self.user

        if self.user and self.group:
            self.user_group = f"{self.user}:{self.group}"

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
            elif keyisset(setting[0], self.definition) and callable(setting[2]):
                setting[2](setting[0])
