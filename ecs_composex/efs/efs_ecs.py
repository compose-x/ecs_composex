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
Module to allow EFS and ECS Linking
"""

from troposphere import Ref, Sub, GetAtt
from troposphere import AWS_URL_SUFFIX, AWS_REGION, AWS_NO_VALUE
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import EFSVolumeConfiguration, Volume as EcsVolume

from ecs_composex.resource_settings import generate_export_strings

from ecs_composex.common import keyisset, LOG
from ecs_composex.common.outputs import get_import_value
from ecs_composex.common.compose_resources import Volume
from ecs_composex.ecs.ecs_params import TASK_T
from ecs_composex.ecs.ecs_template import get_service_family_name
from ecs_composex.ecs.ecs_container_config import (
    assign_resource_envvars_to_service_containers,
)
from ecs_composex.ecs.ecs_params import SG_T
from ecs_composex.efs.efs_params import EFS_ID, EFS_SG_ID_T, NFS_PORT


def add_security_group_ingress(service_stack, fs_name, sg_id=None, port=None):
    """
    Function to add a SecurityGroupIngress rule into the ECS Service template

    :param ecs_composex.ecs.ServicesStack service_stack: The root stack for the services
    :param str fs_name: the name of the database to use for imports
    :param sg_id: The security group Id to use for ingress. DB Security group, not service's
    :param port: The port for Ingress to the DB.
    """
    if sg_id is None:
        sg_id = get_import_value(fs_name, EFS_SG_ID_T)
    if port is None:
        port = NFS_PORT
    SecurityGroupIngress(
        f"AllowFrom{fs_name}to{service_stack.title}",
        template=service_stack.stack_template,
        GroupId=sg_id,
        FromPort=port,
        ToPort=port,
        Description=Sub(f"Allow FROM {service_stack.title} TO {fs_name}"),
        SourceSecurityGroupId=GetAtt(
            service_stack.stack_template.resources[SG_T], "GroupId"
        ),
        SourceSecurityGroupOwnerId=Ref("AWS::AccountId"),
        IpProtocol="6",
    )


def assign_volume_to_task(fs, service, service_stack, compose_content):
    """
    Function to add to the Task definition the Volume configuration for EFS

    :param fs:
    :param service_stack:
    :param compose_content:
    :return:
    """
    the_service = None
    for service_name in compose_content["services"]:
        if service_name == service["name"]:
            the_service = compose_content["services"][service_name]
            break
    if not the_service:
        return
    service_efs = [
        volume
        for volume in the_service.volumes
        if volume["volume"].efs_volume == fs.name
    ]
    if not service_efs:
        return
    volumes_configs = []
    for efs_def in service_efs:
        print(efs_def)
        volume_config = EcsVolume(
            Name=efs_def["source"],
            EFSVolumeConfiguration=EFSVolumeConfiguration(
                FilesystemId=generate_export_strings(fs.logical_name, EFS_ID),
                RootDirectory=Ref(AWS_NO_VALUE)
                if not keyisset("target", efs_def)
                else efs_def["target"],
            ),
        )
        volumes_configs.append(volume_config)
        service_task_def = service_stack.stack_template.resources[TASK_T]
        setattr(service_task_def, "Volumes", volumes_configs)


def assign_volume_to_efs(fs, compose_content):
    """
    Function to add to the Task definition the Volume configuration for EFS

    :param fs:
    :param compose_content:
    :return:
    """
    if not keyisset(Volume.main_key, compose_content):
        LOG.warn("No volumes defined at the top-level, skipping")
        return
    compose_volumes = [
        compose_content[Volume.main_key][name]
        for name in compose_content[Volume.main_key]
        if compose_content[Volume.main_key][name].efs_volume
    ]
    for volume in compose_volumes:
        if not volume.efs_volume == fs.name:
            continue
        LOG.info(f"Mapped volume {volume.name} to EFS {fs.name}")
        volume.cfn_fs = fs


def handle_new_fs(fs, services_stack, services_families, res_root_stack, settings):
    """
    Function to link the FS and the ECS Service.

    :param ecs_composex.efs.efs_template.Efs fs:
    :param services_stack:
    :param services_families:
    :param res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    fs_id = generate_export_strings(fs.logical_name, EFS_ID)
    fs.generate_resource_envvars(
        None,
        arn=Sub(f"${{FsId}}.efs.${{{AWS_REGION}}}.${{{AWS_URL_SUFFIX}}}", FsId=fs_id),
    )
    for service in fs.services:
        service_family = get_service_family_name(services_families, service["name"])
        if service_family not in services_stack.stack_template.resources:
            raise AttributeError(
                f"No service {service_family} present in services stack"
            )
        family_wide = True if service["name"] in services_families else False
        service_stack = services_stack.stack_template.resources[service_family]
        add_security_group_ingress(service_stack, fs.logical_name)
        assign_resource_envvars_to_service_containers(service_stack, fs, family_wide)
        assign_volume_to_task(fs, service, service_stack, settings.compose_content)
        if res_root_stack.title not in services_stack.DependsOn:
            services_stack.DependsOn.append(res_root_stack.title)


def efs_to_ecs(xresources, services_stack, services_families, res_root_stack, settings):
    """
    Function to map EFS to ECS services.

    :param xresources:
    :param services_stack:
    :param services_families:
    :param res_root_stack:
    :param settings:
    :return:
    """
    new_resources = [
        xresources[name] for name in xresources if not xresources[name].lookup
    ]
    lookup_resources = [
        xresources[name] for name in xresources if xresources[name].lookup
    ]
    for new_fs in new_resources:
        assign_volume_to_efs(new_fs, settings.compose_content)
        if not new_fs.services:
            LOG.warn(f"EFS {new_fs.name} does not have any service defined")
            continue
        handle_new_fs(
            new_fs, services_stack, services_families, res_root_stack, settings
        )
    for lookup_fs in lookup_resources:
        if not lookup_fs.services:
            LOG.warn(f"EFS {lookup_fs.name} does not have any service defined")
            continue
