# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module for the ComposeXSettings class
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime as dt
from json import loads
from os import path
from re import compile, sub

import boto3
import jsonschema
import yaml
from botocore.exceptions import ClientError
from cfn_flip.yaml_dumper import LongCleanDumper
from compose_x_common.aws import get_account_id, validate_iam_role_arn
from compose_x_common.compose_x_common import keyisset, set_else_none
from compose_x_render.compose_x_render import ComposeDefinition
from importlib_resources import files as pkg_files
from troposphere import AWSObject

from ecs_composex import __version__
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.aws import get_cross_role_session
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.compose_networks import ComposeNetwork
from ecs_composex.compose.compose_secrets import ComposeSecret
from ecs_composex.compose.compose_services import ComposeService
from ecs_composex.compose.compose_volumes import ComposeVolume
from ecs_composex.compose.x_resources import XResource
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.compose.x_resources.environment_x_resources import (
    AwsEnvironmentResource,
)
from ecs_composex.compose.x_resources.network_x_resources import NetworkXResource
from ecs_composex.compose.x_resources.services_resources import ServicesXResource
from ecs_composex.ecs.ecs_family import ComposeFamily
from ecs_composex.iam import ROLE_ARN_ARG
from ecs_composex.utils.init_ecs import set_ecs_settings
from ecs_composex.utils.init_s3 import create_bucket


class ComposeXSettings:
    """
    Class to handle the settings to use for ECS ComposeX.

    :ivar dict of {str: ComposeFamily} families: Map of families and services
    :ivar ComposeXStack root_stack:
    :ivar ModManager mod_manager:
    """

    name_arg = "Name"
    cluster_name_arg = "ClusterName"

    create_vpc_arg = "CreateVpc"
    create_ec2_arg = "AddComputeResources"

    region_arg = "RegionName"
    zones_arg = "Zones"
    arn_arg = ROLE_ARN_ARG

    deploy_arg = "up"
    render_arg = "render"
    create_arg = "create"
    plan_arg = "plan"
    config_render_arg = "config"
    command_arg = "command"

    bucket_arg = "BucketName"
    input_file_arg = "DockerComposeXFile"
    output_dir_arg = "OutputDirectory"
    format_arg = "TemplateFormat"
    default_format = "json"
    allowed_formats = ["json", "yaml", "text"]
    ecr_arg = "SkipScanEcrImages"

    vpc_cidr_arg = "VpcCidr"
    single_nat_arg = "SingleNat"

    default_vpc_cidr = "100.127.254.0/24"
    default_output_dir = f"/tmp/{dt.utcnow().strftime('%s')}"

    active_commands = [
        {
            "name": deploy_arg,
            "help": "Generates & Validates the CFN templates, Creates/Updates stack in CFN",
        },
        {
            "name": render_arg,
            "help": "Generates & Validates the CFN templates locally. No upload to S3",
        },
        {
            "name": create_arg,
            "help": "Generates & Validates the CFN templates locally. Uploads files to S3",
        },
        {
            "name": plan_arg,
            "help": "Creates a recursive change-set to show the diff prior to an update",
        },
    ]
    validation_commands = [
        {
            "name": config_render_arg,
            "help": "Merges docker-compose files to provide with the final compose content version",
        }
    ]
    neutral_commands = [
        {
            "name": "init",
            "help": "Initializes your AWS Account with prerequisites settings for ECS",
        },
        {"name": "version", "help": "ECS ComposeX Version"},
    ]
    all_commands = active_commands + validation_commands + neutral_commands

    def __init__(
        self,
        content=None,
        profile_name=None,
        session=None,
        for_macro=False,
        **kwargs,
    ):
        """
        Class to init the configuration
        """
        self.__args = deepcopy(kwargs)
        self.for_cfn_macro = for_macro
        self.session = boto3.session.Session()
        self.override_session(session, profile_name, kwargs)
        self.aws_region = (
            kwargs[self.region_arg]
            if keyisset(self.region_arg, kwargs)
            else self.session.region_name
        )

        self.bucket_name = (
            None if not keyisset(self.bucket_arg, kwargs) else kwargs[self.bucket_arg]
        )
        self.volumes = []
        self.services = []
        self.secrets = []
        self.networks = []
        self.secrets_mappings = {}
        self.mappings = {}
        self.families = {}
        self.account_id = None
        self.output_dir = self.default_output_dir
        self.format = self.default_format

        self.requires_private_namespace = False
        self.vpc_cidr = None
        self.single_nat = None
        self.lookup_vpc = False
        self.deploy = True if keyisset(self.deploy_arg, kwargs) else False
        self.plan = True if keyisset(self.plan_arg, kwargs) else False
        self.no_upload = True if keyisset(self.render_arg, kwargs) else False

        self.upload = False if self.no_upload else True
        self.parse_command(kwargs, content)
        self.compose_content = {}
        self.original_content: dict = {}
        self.input_file = (
            kwargs[self.input_file_arg] if keyisset(self.input_file_arg, kwargs) else {}
        )
        self.set_content(kwargs, content)
        self.set_output_settings(kwargs)
        self.use_appmesh = keyisset("x-appmesh", self.compose_content)
        self.evaluate_private_namespace()
        self.name = kwargs[self.name_arg]
        self.ecs_cluster = None
        self.ignore_ecr_findings = keyisset(self.ecr_arg, kwargs)
        self.x_resources_void = []
        self.mod_manager = None
        self.root_stack = None

    @property
    def disable_rollback(self) -> bool:
        return bool(set_else_none("DisableRollback", self.__args, alt_value=False))

    def get_x_resources(self, include_new=True, include_mappings=True) -> list:
        """
        Returns the x_resources with filters

        :param include_new: Whether or not to add the new resources in the list
        :param include_mappings: Whether or not to add the new resources in the listF
        """
        if not include_new and not include_mappings:
            return self.x_resources
        x_resources = []
        for resource in self.x_resources:
            if not include_new and (
                resource.cfn_resource
                and issubclass(type(resource.cfn_resource), AWSObject)
            ):
                continue
            if not include_mappings and resource.mappings:
                continue
            x_resources.append(resource)
        return x_resources

    def find_resource(self, compose_resource_arn: str) -> XResource:
        resource_attribute_match_re = compile(
            r"^(?P<res_key>x-[\S]+)::(?P<res_name>[\S]+)$"
        )
        parts = resource_attribute_match_re.match(compose_resource_arn)
        if not parts:
            raise ValueError(
                compose_resource_arn,
                "does not match",
                resource_attribute_match_re.pattern,
            )
        for resource in self.x_resources:
            if resource.module.res_key == parts.group(
                "res_key"
            ) and resource.name == parts.group("res_name"):
                return resource
        raise LookupError(
            "Unable to find any resource matching",
            compose_resource_arn,
            self.x_resource_repr,
            type(compose_resource_arn),
        )

    def get_resource_attribute(self, compose_resource_arn: str) -> tuple:
        import re

        resource_attribute_match_re = re.compile(
            r"^(?P<res_key>x-[\S]+)::(?P<res_name>[\S]+)::(?P<return_value>[\S]+)$"
        )
        parts = resource_attribute_match_re.match(compose_resource_arn)
        if not parts:
            LOG.error(
                f"{compose_resource_arn} if invalid. Must match, {resource_attribute_match_re.pattern}"
            )
            return None, None
        try:
            resource = self.find_resource(
                f"{parts.group('res_key')}::{parts.group('res_name')}"
            )
            if (
                parts.group("return_value")
                not in resource.property_to_parameter_mapping
            ):
                raise KeyError(
                    parts.group("return_value"),
                    "not a valid return value for",
                    resource.module.res_key,
                    resource.name,
                    resource.property_to_parameter_mapping.keys(),
                )
            parameter = resource.property_to_parameter_mapping[
                parts.group("return_value")
            ]
            return resource, parameter
        except LookupError:
            return None, None

    @property
    def x_resource_repr(self):
        return [f"{_r.module.res_key}.{_r.name}" for _r in self.x_resources]

    @property
    def stacks(self):
        _stacks = {}
        for resource_name, resource in self.root_stack.stack_template.resources.items():
            if isinstance(resource, ComposeXStack) or issubclass(
                type(resource), ComposeXStack
            ):
                _stacks[resource.title] = resource
        return _stacks

    @property
    def x_resources(self):
        """
        Iterates over all resources defined and returns the list of them
        Only resources that are created from XResource(and children classes) are considered.
        Avoids having to go through stacks down to resources and work backwards

        Returns: the list of XResource in the execution.

        """
        _resources = []
        for name, module in self.mod_manager.modules.items():
            _resources += module.resources_list
        return _resources

        # all_keys = self.compose_content.keys()
        # all_resources = []
        # for res_key in all_keys:
        #
        #     if not isinstance(self.compose_content[res_key], dict):
        #         continue
        #     for resource in self.compose_content[res_key].values():
        #         if not issubclass(
        #             type(resource),
        #             (
        #                 XResource,
        #                 ServicesXResource,
        #                 NetworkXResource,
        #                 ApiXResource,
        #                 AwsEnvironmentResource,
        #             ),
        #         ):
        #             continue
        #         all_resources.append(resource)
        # return all_resources

    def evaluate_private_namespace(self):
        """
        Method to go over all services and figure out if any of them requires cloudmap.
        If so it will also expect x-dns.PrivateNamespace to be set.
        """
        self.requires_private_namespace = self.use_appmesh or any(
            keyisset("x-cloudmap", service.x_network) for service in self.services
        )
        if self.requires_private_namespace:
            LOG.warning(
                "At least one service requires cloudmap or AppMesh is used. Enabling private namespace"
            )

    def requires_vpc(self):
        """
        Determines whether the execution will require a VPC.
        """
        x_resources_require_vpc = any([res.requires_vpc for res in self.x_resources])
        services_require_vpc = any(
            [
                family.service_compute.launch_type != "EXTERNAL"
                for family in self.families.values()
                if (family and family.ecs_service)
            ]
        )
        return any([x_resources_require_vpc, services_require_vpc])

    def set_secrets(self) -> None:
        """
        Function to parse the settings compose content and define the secrets.
        """
        if not keyisset(ComposeSecret.main_key, self.compose_content):
            return
        for secret_name in self.compose_content[ComposeSecret.main_key]:
            secret_def = self.compose_content[ComposeSecret.main_key][secret_name]
            if keyisset(ComposeSecret.x_key, secret_def) and isinstance(
                secret_def[ComposeSecret.x_key], dict
            ):
                LOG.info(f"Adding secret {secret_name} to settings")
                secret = ComposeSecret(secret_name, secret_def, self)
                self.secrets.append(secret)
                self.compose_content[ComposeSecret.main_key][secret_name] = secret

    def set_efs(self) -> None:
        """
        Method to add a x-efs definition to the compose-x definition when a volume is flagged as using NFS/EFS
        """
        if (
            not self.volumes
            or not keyisset(ComposeVolume.main_key, self.compose_content)
            or not self.compose_content[ComposeVolume.main_key]
        ):
            return
        if not keyisset("x-efs", self.compose_content):
            efs = {}
            self.compose_content["x-efs"] = efs
        else:
            efs = self.compose_content["x-efs"]
        for volume in self.compose_content[ComposeVolume.main_key].values():
            if volume.lookup or volume.use:
                continue
            if (
                volume.efs_definition
                or volume.driver == "nfs"
                or volume.driver == "efs"
            ):
                if not keyisset(volume.name, efs):
                    efs[volume.name] = {
                        "Properties": volume.efs_definition,
                        "MacroParameters": volume.parameters,
                        "Lookup": volume.lookup,
                        "Services": [
                            {"name": service.name, "access": "RW"}
                            for service in volume.services
                        ],
                        "Settings": {"Subnets": "StorageSubnets"},
                        "Volume": volume,
                    }
                else:
                    LOG.warning(
                        f"x-efs {volume.name} was already defined in top-level x-efs. Not overriding from volumes"
                    )

    def set_volumes(self) -> None:
        """
        Method configuring the volumes at root level
        :return:
        """
        if not keyisset(ComposeVolume.main_key, self.compose_content):
            LOG.debug("No volumes detected at the root level of compose file")
            return
        for volume_name in self.compose_content[ComposeVolume.main_key]:
            volume = ComposeVolume(
                volume_name,
                self.compose_content[ComposeVolume.main_key][volume_name],
            )
            self.compose_content[ComposeVolume.main_key][volume_name] = volume
            self.volumes.append(volume)

    def set_networks(self, vpc_stack) -> None:
        """
        Maps top level docker-compose networks with x-vpc subnets when applicable.
        """
        if not keyisset(ComposeNetwork.main_key, self.compose_content):
            LOG.debug("No networks detected at the root level of compose file")
            return
        networks = self.compose_content[ComposeNetwork.main_key]
        for network_name, definition in networks.items():
            network = ComposeNetwork(
                network_name,
                definition,
                vpc_stack.vpc_resource.subnets_parameters,
            )
            networks[network_name] = network
            self.networks.append(network)

    def set_services(self) -> None:
        """
        Method to define the ComposeXResource for each service.
        :return:
        """
        if not keyisset(ComposeService.main_key, self.compose_content):
            return
        for service_name in self.compose_content[ComposeService.main_key]:
            service = ComposeService(
                service_name,
                self.compose_content[ComposeService.main_key][service_name],
                self.volumes,
                self.secrets,
            )
            self.compose_content[ComposeService.main_key][service_name] = service
            self.services.append(service)
            service.image.interpolate_image_digest(self)

    def add_new_family(
        self, family_name: str, service: ComposeService, assigned_services: list
    ) -> None:
        if service in assigned_services:
            LOG.info(
                f"New family {family_name} - "
                f"Detected {service.name} has multiple families defined. Making a duplicate"
            )
            the_service = deepcopy(service)
            family = ComposeFamily([the_service], family_name)
            self.families[family.logical_name] = family
            the_service.family = family
            self.services.append(the_service)
        else:
            family = ComposeFamily([service], family_name)
            service.family = family
            if service not in assigned_services:
                assigned_services.append(service)
        self.families[family.logical_name] = family

    def add_service_to_family(
        self, family_name: str, service: ComposeService, assigned_services: list
    ) -> None:
        the_family = self.families[family_name]
        if service in assigned_services:
            LOG.info(
                f"New family {family_name} - "
                f"Detected {service.name} has multiple families defined. Making a duplicate"
            )
            the_service = deepcopy(service)
            self.services.append(the_service)
        else:
            the_service = service
        LOG.debug(f"THE_SERVICE, {hex(id(the_service))}, SERVICE, {hex(id(service))}")
        the_family.add_service(the_service)
        the_service.family = the_family
        if the_service not in assigned_services:
            assigned_services.append(the_service)

    def set_families(self) -> None:
        """
        Method to define the list of families.
        Creating services_to_assign which won't get duplicate services added, as they already are in other functions.
        """
        assigned_services = []
        services_to_assign = [_service for _service in self.services]
        for service in services_to_assign:
            for family_name in service.families:
                formatted_name = sub(r"[^a-zA-Z0-9]+", "", family_name)
                if NONALPHANUM.findall(formatted_name):
                    raise ValueError(
                        "Family names must be ^[a-zA-Z0-9]+$ | alphanumerical"
                    )
                if formatted_name not in self.families:
                    self.add_new_family(family_name, service, assigned_services)
                elif formatted_name in self.families.keys():
                    family_services = [
                        _service.name
                        for _service in self.families[formatted_name].ordered_services
                    ]
                    if service.name not in family_services:
                        self.add_service_to_family(
                            formatted_name, service, assigned_services
                        )
        LOG.debug([self.families[family] for family in self.families])

    def set_content(self, kwargs, content=None, fully_load=True):
        """
        Method to initialize the compose content

        :param dict kwargs:
        :param dict content:
        :param bool fully_load:
        """
        files = (
            []
            if not keyisset(self.input_file_arg, kwargs)
            else kwargs[self.input_file_arg]
        )
        LOG.debug(f"Input files: {files}")
        content_def = ComposeDefinition(files, content)
        self.original_content = content_def.definition
        self.compose_content = deepcopy(content_def.definition)
        source = pkg_files("ecs_composex").joinpath("specs/compose-spec.json")
        LOG.info(f"Validating against input schema {source}")
        resolver = jsonschema.RefResolver(
            f"file://{path.abspath(path.dirname(source))}/", None
        )
        jsonschema.validate(
            content_def.definition,
            loads(source.read_text()),
            resolver=resolver,
        )
        if fully_load:
            self.set_secrets()
            self.set_volumes()
            self.set_services()
            self.set_families()
            self.set_efs()

    def parse_command(self, kwargs, content=None):
        """
        Method to analyze the command and set execution settings accordingly.

        :param dict kwargs:
        :param dict content:
        :return:
        """
        command = kwargs[self.command_arg]
        command_names = [cmd["name"] for cmd in self.all_commands]
        if command not in command_names:
            exit(1)
        if command == self.deploy_arg:
            self.deploy = True
            self.upload = True
        elif command == self.plan_arg:
            self.plan = True
            self.upload = True
        elif command == self.render_arg:
            self.no_upload = True
            self.upload = not self.no_upload
        elif command == self.create_arg:
            self.no_upload = False
            self.upload = not self.no_upload
        elif command == self.config_render_arg:
            self.set_content(kwargs, content, fully_load=False)
            print(yaml.dump(self.compose_content, Dumper=LongCleanDumper))
            exit()
        elif command == "version":
            print("ECS ComposeX", __version__)
            exit(0)
        elif command == "init":
            set_ecs_settings(self.session)
            self.init_s3()
            exit(0)

    def override_session(self, session, profile_name, kwargs):
        """
        Method to set the session based on input params

        :param boto3.session.Session session: The session to override the API calls with
        :param str profile_name: Name of a profile configured in .aws/config
        :param dict kwargs: CLI kwargs
        """
        if profile_name and not session:
            self.session = boto3.session.Session(profile_name=profile_name)
        elif session and not (profile_name or keyisset(self.arn_arg, kwargs)):
            self.session = session
        if keyisset(self.arn_arg, kwargs):
            validate_iam_role_arn(arn=kwargs[self.arn_arg])
            if session:
                self.session = get_cross_role_session(
                    session,
                    kwargs[ROLE_ARN_ARG],
                    session_name=f"ComposeXSettings@{kwargs[self.command_arg]}",
                )
            else:
                self.session = get_cross_role_session(
                    self.session,
                    kwargs[ROLE_ARN_ARG],
                    session_name=f"ComposeXSettings@{kwargs[self.command_arg]}",
                )

    def set_output_settings(self, kwargs):
        """
        Method to set the output settings based on kwargs
        """
        self.format = self.default_format
        if (
            keyisset(self.format_arg, kwargs)
            and kwargs[self.format_arg] in self.allowed_formats
        ):
            self.format = kwargs[self.format_arg]

        self.output_dir = (
            kwargs[self.output_dir_arg]
            if keyisset(self.output_dir_arg, kwargs)
            else self.default_output_dir
        )

    def set_bucket_name_from_account_id(self):
        """
        Defines the default bucket name to use from the AWS Account ID
        """
        if self.bucket_name and isinstance(self.bucket_name, str):
            return
        if self.account_id is None:
            try:
                self.account_id = get_account_id(session=self.session)
                self.bucket_name = f"ecs-composex-{self.account_id}-{self.aws_region}"
            except ClientError as error:
                code = error.response["Error"]["Code"]
                message = error.response["Error"]["Message"]
                if code == "ExpiredToken":
                    LOG.error(message)
                    LOG.warning(
                        "Due to credentials error, we won't attempt to upload to S3."
                    )
                else:
                    LOG.error(error)
                self.bucket_name = None
                self.upload = False
                self.no_upload = True

    def init_s3(self):
        """
        Method to initialize S3 settings

        :return:
        """
        self.set_bucket_name_from_account_id()
        if self.bucket_name:
            create_bucket(self.bucket_name, self.session)
