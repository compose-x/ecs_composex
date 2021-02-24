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

from troposphere import Ref, GetAtt
from troposphere import Parameter
from troposphere.ecs import EFSVolumeConfiguration, Volume, AuthorizationConfig
from troposphere.efs import AccessPoint
from troposphere.iam import Policy, PolicyType

from ecs_composex.common import add_parameters, keyisset
from ecs_composex.ecs.ecs_params import TASK_T, TASK_ROLE_T, SERVICE_T
from ecs_composex.tcp_resources_settings import handle_new_tcp_resource
from ecs_composex.efs.efs_params import FS_PORT, FS_REGEXP, FS_MNT_PT_SG_ID, FS_ID


def add_task_iam_access_to_access_point(family, access_point, efs):
    """
    Function to add IAM Permissions to mount to EFS via AccessPoint for ECS Task

    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param troposphere.efs.AccessPoint access_point:
    :param ecs_composex.efs.efs_stack.Efs efs:
    """
    task_role = family.template.resources[TASK_ROLE_T]
    service_definition = family.template.resources[SERVICE_T]
    service_depends_on = (
        getattr(service_definition, "DependsOn")
        if hasattr(service_definition, "DependsOn")
        else []
    )
    if not service_depends_on:
        setattr(service_definition, "DependsOn", service_depends_on)
    policy = PolicyType(
        f"{access_point.title}IamAccess",
        PolicyName=f"IamAccessToEfs{efs.logical_name}",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": f"{family.logical_name}EfsAccess",
                    "Effect": "Allow",
                    "Action": [
                        "elasticfilesystem:ClientMount",
                        "elasticfilesystem:ClientWrite",
                    ],
                    "Condition": {
                        "StringEquals": {
                            "elasticfilesystem:AccessPointArn": GetAtt(
                                access_point, "Arn"
                            )
                        }
                    },
                }
            ],
        },
        Roles=[Ref(task_role)],
    )
    service_depends_on.append(policy.title)


def expand_family_with_efs_volumes(efs_root_stack_title, new_efs, settings):
    """
    Function to add the EFS Volume definition to the task definition for the service to use.

    :param efs_root_stack_title: Root stack title for EFS
    :param new_efs:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    fs_id_parameter = new_efs.attributes_outputs[FS_ID]["ImportParameter"]
    fs_id_getatt = new_efs.attributes_outputs[FS_ID]["ImportValue"]
    for target in new_efs.families_targets:
        target[0].stack.Parameters.update({fs_id_parameter.title: fs_id_getatt})
        add_parameters(target[0].template, [fs_id_parameter])
        task_definition = target[0].template.resources[TASK_T]
        efs_config_kwargs = {"FilesystemId": Ref(fs_id_parameter)}
        if new_efs.parameters and keyisset("EnforceIamAuth", new_efs.parameters):
            efs_access_point = target[0].template.add_resource(
                AccessPoint(
                    f"{new_efs.logical_name}{target[0].logical_name}EfsAccessPoint",
                    FileSystemId=Ref(fs_id_parameter),
                )
            )
            add_task_iam_access_to_access_point(target[0], efs_access_point, new_efs)
            efs_config_kwargs.update(
                {
                    "AuthorizationConfig": AuthorizationConfig(
                        AccessPointId=Ref(efs_access_point), IAM="ENABLED"
                    ),
                    "TransitEncryption": "ENABLED",
                }
            )
        efs_volume_definition = Volume(
            EFSVolumeConfiguration=EFSVolumeConfiguration(**efs_config_kwargs),
            Name=new_efs.volume.volume_name,
        )
        volumes = (
            getattr(task_definition, "Volumes")
            if (hasattr(task_definition, "Volumes"))
            else []
        )
        if not volumes:
            setattr(task_definition, "Volumes", volumes)
        volumes.append(efs_volume_definition)


def efs_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to associate back the EFS FS to services.

    :param resources:
    :param services_stack:
    :param res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """

    efs_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].lookup
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(
            new_res,
            res_root_stack,
            port_parameter=FS_PORT,
            sg_parameter=FS_MNT_PT_SG_ID,
        )
        expand_family_with_efs_volumes(res_root_stack.title, new_res, settings)
