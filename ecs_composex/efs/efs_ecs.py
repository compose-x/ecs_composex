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
from troposphere import AWS_URL_SUFFIX, AWS_REGION
from troposphere.ec2 import SecurityGroupIngress

from ecs_composex.resource_settings import generate_export_strings
from ecs_composex.common import LOG
from ecs_composex.common.outputs import get_import_value
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


def handle_new_fs(fs, services_stack, services_families, res_root_stack):
    """
    Function to link the FS and the ECS Service.

    :param ecs_composex.efs.efs_template.Efs fs:
    :param services_stack:
    :param services_families:
    :param res_root_stack:
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
        service_template = service_stack.stack_template
        add_security_group_ingress(service_stack, fs.logical_name)
        assign_resource_envvars_to_service_containers(service_stack, fs, family_wide)
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
        if not new_fs.services:
            LOG.warn(f"EFS {new_fs.name} does not have any service defined")
            continue
        handle_new_fs(new_fs, services_stack, services_families, res_root_stack)
    for lookup_fs in lookup_resources:
        if not lookup_fs.services:
            LOG.warn(f"EFS {lookup_fs.name} does not have any service defined")
            continue
