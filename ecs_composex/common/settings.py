#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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
Module for the ComposeXSettings class
"""

from re import sub
from copy import deepcopy
from datetime import datetime as dt

import boto3
import yaml
from botocore.exceptions import ClientError
from cfn_flip.yaml_dumper import LongCleanDumper

from ecs_composex import __version__
from ecs_composex.ingress_settings import set_service_ports
from ecs_composex.common import keyisset, LOG, load_composex_file, NONALPHANUM
from ecs_composex.common.aws import get_account_id, get_region_azs
from ecs_composex.common.aws import get_cross_role_session
from ecs_composex.common.cfn_params import USE_FLEET_T
from ecs_composex.secrets.compose_secrets import ComposeSecret
from ecs_composex.common.compose_services import (
    ComposeService,
    ComposeFamily,
)
from ecs_composex.common.compose_volumes import ComposeVolume
from ecs_composex.common.compose_networks import ComposeNetwork
from ecs_composex.common.envsubst import expandvars
from ecs_composex.iam import ROLE_ARN_ARG
from ecs_composex.iam import validate_iam_role_arn
from ecs_composex.utils.init_ecs import set_ecs_settings
from ecs_composex.utils.init_s3 import create_bucket
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    APP_SUBNETS,
    PUBLIC_SUBNETS,
    STORAGE_SUBNETS,
)


def render_services_ports(services):
    """
    Function to set and render ports as docker-compose does for config

    :param dict services:
    :return:
    """
    for service_name in services:
        if keyisset("ports", services[service_name]):
            ports = set_service_ports(services[service_name]["ports"])
            services[service_name]["ports"] = ports


def merge_ports(source_ports, new_ports):
    """
    Function to merge two sections of ports

    :param list source_ports:
    :param list new_ports:
    :return:
    """
    f_source_ports = set_service_ports(source_ports)
    f_override_ports = set_service_ports(new_ports)
    f_overide_ports_targets = [port["target"] for port in f_override_ports]
    new_ports = []
    for port in f_override_ports:
        new_ports.append(port)
        for s_port in f_source_ports:
            if s_port["target"] not in f_overide_ports_targets:
                new_ports.append(s_port)
    return new_ports


def merge_service_definition(original_def, override_def, nested=False):
    """
    Merges two services definitions if service exists in both compose files.

    :param bool nested:
    :param dict original_def:
    :param dict override_def:
    :return:
    """

    if not nested:
        original_def = deepcopy(original_def)
    for key in override_def.keys():
        if (
            isinstance(override_def[key], dict)
            and keyisset(key, original_def)
            and isinstance(original_def[key], dict)
        ):
            merge_service_definition(original_def[key], override_def[key], nested=True)
        elif key not in original_def:
            original_def[key] = override_def[key]
        elif (
            isinstance(override_def[key], list)
            and key in original_def.keys()
            and key != "ports"
        ):
            if not isinstance(original_def[key], list):
                raise TypeError(
                    "Cannot merge",
                    key,
                    "from",
                    type(original_def[key]),
                    "with",
                    type(override_def[key]),
                )
            original_def[key] = handle_lists_merges(
                original_def[key], override_def[key]
            )
        elif (
            isinstance(override_def[key], list)
            and key in original_def.keys()
            and key == "ports"
        ):
            original_def[key] = merge_ports(original_def[key], override_def[key])
        elif isinstance(override_def[key], str):
            original_def[key] = expandvars(override_def[key])
        else:
            original_def[key] = override_def[key]
    return original_def


def interpolate_env_vars(content):
    """
    Function to interpolate env vars from content

    :param dict content:
    :return:
    """
    if not content:
        return
    for key in content.keys():
        if isinstance(content[key], dict):
            interpolate_env_vars(content[key])
        elif isinstance(content[key], list):
            for count, item in enumerate(content[key]):
                if isinstance(item, dict):
                    interpolate_env_vars(item)
                elif isinstance(item, str):
                    content[key][count] = expandvars(item)
        elif isinstance(content[key], str):
            content[key] = expandvars(content[key], default="")


def merge_services_from_files(original_services, override_services):
    """
    Function to merge two docker compose files content.

    """
    for service_name in override_services:
        if keyisset(service_name, original_services):
            original_services.update(
                {
                    service_name: merge_service_definition(
                        original_services[service_name],
                        override_services[service_name],
                    )
                }
            )
        else:
            original_services.update({service_name: override_services[service_name]})


def handle_lists_merges(original_list, override_list, uniqfy=False):
    """

    :param list original_list: The original list to add the override ones to
    :param list override_list: The lost of items to add up
    :param bool uniqfy: Whether you are expecting identical dicts which should be filtered to be uniqu based on values.
    :return: The merged list
    :rtype: list
    """
    final_list = []

    final_list += [item for item in original_list if isinstance(item, dict)]
    final_list += [item for item in override_list if isinstance(item, dict)]
    if uniqfy:
        final_list = [dict(y) for y in set(tuple(x.items()) for x in final_list)]
    original_str_items = [item for item in original_list if isinstance(item, list)]
    final_list += list(
        set(
            original_str_items
            + [item for item in override_list if isinstance(item, list)]
        )
    )

    origin_list_items = [item for item in original_list if isinstance(item, list)]
    override_list_items = [item for item in override_list if isinstance(item, list)]

    if origin_list_items and override_list_items:
        merged_lists = handle_lists_merges(origin_list_items, override_list_items)
        final_list += merged_lists
    elif origin_list_items and not override_list_items:
        final_list += origin_list_items
    elif not origin_list_items and override_list_items:
        final_list += override_list_items
    return final_list


def handle_lists_merge_conditions(original_def, override_def, key):
    """
    Function to handle lists merging and whether some additional handling is necessary for duplicates

    :param dict original_def: The src definition
    :param dict override_def: The override definition to merge to src.
    :param str key: The key name of the list object
    """
    keys_to_uniqfy = ["Tags", "volumes", "secrets"]
    if not isinstance(original_def[key], list):
        raise TypeError(
            "Cannot merge",
            key,
            "from",
            type(original_def[key]),
            "with",
            type(override_def[key]),
        )
    if key in keys_to_uniqfy:
        original_def[key] = handle_lists_merges(
            original_def[key], override_def[key], uniqfy=True
        )
    else:
        original_def[key] = handle_lists_merges(
            original_def[key], override_def[key], uniqfy=False
        )


def merge_definitions(original_def, override_def, nested=False):
    """
    Merges two services definitions if service exists in both compose files.

    :param bool nested:
    :param dict original_def:
    :param dict override_def:
    :return:
    """
    if not nested:
        original_def = deepcopy(original_def)
    elif not isinstance(override_def, dict):
        raise TypeError("Expected", dict, "got", type(override_def))
    for key in override_def.keys():
        if (
            isinstance(override_def[key], dict)
            and keyisset(key, original_def)
            and isinstance(original_def[key], dict)
        ):
            merge_definitions(original_def[key], override_def[key], nested=True)
        elif key not in original_def:
            original_def[key] = override_def[key]
        elif isinstance(override_def[key], list) and key in original_def.keys():
            handle_lists_merge_conditions(original_def, override_def, key)
        elif isinstance(override_def[key], list) and key not in original_def.keys():
            original_def[key] = override_def[key]

        elif isinstance(override_def[key], str):
            original_def[key] = expandvars(override_def[key])
        else:
            original_def[key] = override_def[key]
    return original_def


def merge_config_files(original_content, override_content):
    """
    Function to merge everything that is not services

    :param dict original_content:
    :param dict override_content:
    :return:
    """

    for compose_key in override_content:
        if (
            compose_key == ComposeService.main_key
            and keyisset(compose_key, original_content)
            and keyisset(compose_key, override_content)
        ):
            original_services = original_content[ComposeService.main_key]
            override_services = override_content[ComposeService.main_key]
            merge_services_from_files(original_services, override_services)

        elif (
            keyisset(compose_key, original_content)
            and isinstance(original_content[compose_key], dict)
            and not compose_key == ComposeService.main_key
        ):
            original_definition = deepcopy(original_content[compose_key])
            override_definition = override_content[compose_key]
            original_content.update(
                {
                    compose_key: merge_definitions(
                        original_definition,
                        override_definition,
                    )
                }
            )
        elif not keyisset(compose_key, original_content):
            original_content[compose_key] = override_content[compose_key]


class ComposeXSettings(object):
    """
    Class to handle the settings to use for ECS ComposeX.
    """

    name_arg = "Name"
    cluster_name_arg = "ClusterName"

    create_vpc_arg = "CreateVpc"
    create_ec2_arg = "AddComputeResources"
    create_spotfleet_arg = USE_FLEET_T

    region_arg = "RegionName"
    zones_arg = "Zones"
    arn_arg = ROLE_ARN_ARG

    deploy_arg = "up"
    render_arg = "render"
    create_arg = "create"
    config_render_arg = "config"
    command_arg = "command"

    bucket_arg = "BucketName"
    input_file_arg = "DockerComposeXFile"
    output_dir_arg = "OutputDirectory"
    format_arg = "TemplateFormat"
    default_format = "json"
    allowed_formats = ["json", "yaml", "text"]

    vpc_cidr_arg = "VpcCidr"
    single_nat_arg = "SingleNat"

    default_vpc_cidr = "100.127.254.0/24"
    default_azs = ["eu-west-1a", "eu-west-1b"]
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
        self, content=None, profile_name=None, session=None, for_macro=False, **kwargs
    ):
        """
        Class to init the configuration
        """
        self.for_cfn_macro = for_macro
        self.session = boto3.session.Session()
        self.override_session(session, profile_name, kwargs)
        self.aws_region = (
            kwargs[self.region_arg]
            if keyisset(self.region_arg, kwargs)
            else self.session.region_name
        )
        self.aws_azs = self.default_azs
        self.public_azs = self.default_azs
        self.app_azs = self.default_azs
        self.storage_azs = self.default_azs

        self.bucket_name = (
            None if not keyisset(self.bucket_arg, kwargs) else kwargs[self.bucket_arg]
        )
        self.volumes = []
        self.services = []
        self.secrets = []
        self.networks = []
        self.subnets_parameters = []
        self.subnets_mappings = {}
        self.secrets_mappings = {}
        self.mappings = {}
        self.families = {}
        self.account_id = None
        self.output_dir = self.default_output_dir
        self.format = self.default_format

        self.create_vpc = False
        self.vpc_cidr = None
        self.single_nat = None
        self.lookup_vpc = False
        self.deploy = True if keyisset(self.deploy_arg, kwargs) else False
        self.no_upload = True if keyisset(self.render_arg, kwargs) else False

        self.upload = False if self.no_upload else True
        self.create_compute = False if not keyisset(USE_FLEET_T, kwargs) else True
        self.parse_command(kwargs, content)
        self.compose_content = {}
        self.input_file = (
            kwargs[self.input_file_arg] if keyisset(self.input_file_arg, kwargs) else {}
        )
        self.set_content(kwargs, content)
        self.set_output_settings(kwargs)
        self.use_appmesh = keyisset("x-appmesh", self.compose_content)
        self.name = kwargs[self.name_arg]
        self.ecs_cluster = None

    def set_secrets(self):
        """
        Function to parse the settings compose content and define the secrets.

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :return:
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

    def set_volumes(self):
        """
        Method configuring the volumes at root level
        :return:
        """
        if not keyisset(ComposeVolume.main_key, self.compose_content):
            LOG.debug("No volumes detected at the root level of compose file")
            return
        for volume_name in self.compose_content[ComposeVolume.main_key]:
            volume = ComposeVolume(
                volume_name, self.compose_content[ComposeVolume.main_key][volume_name]
            )
            self.compose_content[ComposeVolume.main_key][volume_name] = volume
            self.volumes.append(volume)

    def set_networks(self, vpc_stack, root_stack):
        """
        Method configuring the networks defined at root level
        :return:
        """
        if not keyisset(ComposeNetwork.main_key, self.compose_content):
            LOG.debug("No networks detected at the root level of compose file")
            return
        elif vpc_stack:
            LOG.info(
                "ComposeX will be creating the VPC, therefore networks are ignored!"
            )
            return
        for network_name in self.compose_content[ComposeNetwork.main_key]:
            network = ComposeNetwork(
                network_name,
                self.compose_content[ComposeNetwork.main_key][network_name],
                self.subnets_parameters,
            )
            self.compose_content[ComposeNetwork.main_key][network_name] = network
            self.networks.append(network)

    def set_services(self):
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

    def add_new_family(self, family_name, service, assigned_services):
        if service.name in [service.name for service in assigned_services]:
            LOG.info(
                f"Detected {service.name} is-reused in different family. Making a deepcopy"
            )
            the_service = deepcopy(service)
            family = ComposeFamily([the_service], family_name)
            self.families[family.logical_name] = family
            the_service.my_family = family
            self.services.append(the_service)
        else:
            family = ComposeFamily([service], family_name)
            service.my_family = family
        self.families[family.logical_name] = family
        if service.name not in [service.name for service in assigned_services]:
            assigned_services.append(service)

    def handle_assigned_existing_service(self, family_name, service, assigned_services):
        the_family = self.families[family_name]
        if service.name in [service.name for service in assigned_services]:
            LOG.info(
                f"Detected {service.name} is-reused in different family. Making a deepcopy"
            )

            the_service = deepcopy(service)
            the_family.add_service(the_service)
            the_service.my_family = self.families[family_name]
            self.services.append(the_service)
        else:
            the_family.add_service(service)
            service.my_family = self.families[family_name]
            assigned_services.append(service)

    def set_families(self):
        """
        Method to define the list of families
        :return:
        """
        assigned_services = []
        for service in self.services:
            for family_name in service.families:
                formatted_name = sub(r"[^a-zA-Z0-9]+", "", family_name)
                if NONALPHANUM.findall(formatted_name):
                    raise ValueError(
                        "Family names must be ^[a-zA-Z0-9]+$ | alphanumerical"
                    )
                if formatted_name not in self.families.keys():
                    self.add_new_family(family_name, service, assigned_services)
                elif formatted_name in self.families.keys() and service.name not in [
                    service.name for service in self.families[formatted_name].services
                ]:
                    self.handle_assigned_existing_service(
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
        if content is None and len(kwargs[self.input_file_arg]) == 1:
            self.compose_content = load_composex_file(kwargs[self.input_file_arg][0])
        elif content is None and len(kwargs[self.input_file_arg]) > 1:
            files_list = kwargs[self.input_file_arg]
            self.compose_content = load_composex_file(files_list[0])
            files_list.pop(0)
            for file in files_list:
                merge_config_files(self.compose_content, load_composex_file(file))
                LOG.debug(yaml.dump(self.compose_content))

        elif content and isinstance(content, dict):
            self.compose_content = content
        if keyisset(ComposeService.main_key, self.compose_content):
            render_services_ports(self.compose_content[ComposeService.main_key])
        LOG.debug(yaml.dump(self.compose_content))
        interpolate_env_vars(self.compose_content)
        if fully_load:
            self.set_secrets()
            self.set_volumes()
            self.set_services()
            self.set_families()

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

    def set_azs_from_api(self):
        """
        Method to set the AWS Azs based on DescribeAvailabilityZones
        :return:
        """
        try:
            self.aws_azs = get_region_azs(self.session)
        except ClientError as error:
            code = error.response["Error"]["Code"]
            message = error.response["Error"]["Message"]
            if code == "RequestExpired":
                LOG.error(message)
                LOG.warning(f"Due to error, using default values {self.aws_azs}")

            else:
                LOG.error(error)

    def set_azs_from_vpc_import(
        self, public_subnets, app_subnets, storage_subnets, session=None
    ):
        """
        Function to get the list of AZs for a given set of subnets

        :param list public_subnets:
        :param list app_subnets:
        :param list storage_subnets:
        :param session: The Session used to find the EC2 subnets (useful for lookup).
        :return:
        """
        if session is None:
            client = self.session.client("ec2")
        else:
            client = session.client("ec2")
        try:
            public_r = client.describe_subnets(SubnetIds=public_subnets)["Subnets"]
            app_r = client.describe_subnets(SubnetIds=app_subnets)["Subnets"]
            storage_r = client.describe_subnets(SubnetIds=storage_subnets)["Subnets"]
            self.public_azs = [sub["AvailabilityZone"] for sub in public_r]
            self.subnets_mappings[PUBLIC_SUBNETS.title]["Azs"] = self.public_azs
            self.storage_azs = [sub["AvailabilityZone"] for sub in storage_r]
            self.subnets_mappings[STORAGE_SUBNETS.title]["Azs"] = self.storage_azs
            self.app_azs = [sub["AvailabilityZone"] for sub in app_r]
            self.subnets_mappings[APP_SUBNETS.title]["Azs"] = self.app_azs
            LOG.info("Successfully updated self with AZs from looked up VPC subnets")
        except ClientError:
            LOG.warning("Could not define the AZs based on the imported subnets")

    def set_bucket_name_from_account_id(self):
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
