# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.efs.efs_stack import Efs

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import GetAtt, Ref
from troposphere.ecs import AuthorizationConfig, EFSVolumeConfiguration, Volume
from troposphere.efs import AccessPoint, CreationInfo, PosixUser, RootDirectory
from troposphere.iam import PolicyType

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_parameters, add_resource
from ecs_composex.ecs.ecs_params import TASK_T
from ecs_composex.efs.efs_params import FS_ARN, FS_ID, FS_MNT_PT_SG_ID, FS_PORT
from ecs_composex.rds_resources_settings import (
    add_security_group_ingress,
    handle_new_tcp_resource,
)


def get_volumes(task_definition):
    """
    Function to fetch the volumes from the task definition

    :param troposphere.ecs.TaskDefinition task_definition:
    :return: the volumes list of the task definition or new ones
    :rtype: list
    """
    volumes = (
        getattr(task_definition, "Volumes")
        if (hasattr(task_definition, "Volumes"))
        else []
    )
    if not volumes:
        setattr(task_definition, "Volumes", volumes)
    return volumes


def get_service_mount_points(service):
    """
    Function to get the MountPoints from the container definition of a service

    :param ecs_composex.common.compose_services.ComposeService service:
    :return: list of mount points or new list
    :rtype: list
    """
    mount_points = []
    if not hasattr(service.container_definition, "MountPoints"):
        setattr(service.container_definition, "MountPoints", mount_points)
    else:
        mount_points = getattr(service.container_definition, "MountPoints")
    return mount_points


def add_task_iam_access_to_access_point(family, access_points, efs):
    """
    Function to add IAM Permissions to mount to EFS via AccessPoint for ECS Task

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param list<troposphere.efs.AccessPoint> access_points:
    :param ecs_composex.efs.efs_stack.Efs efs:
    """
    policy = PolicyType(
        f"{family.logical_name}IamAccess",
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
                        "elasticfilesystem:ClientRootAccess",
                    ],
                    "Resource": [
                        Ref(efs.attributes_outputs[FS_ARN]["ImportParameter"])
                    ],
                    "Condition": {
                        "StringEquals": {
                            "elasticfilesystem:AccessPointArn": [
                                GetAtt(access_point, "Arn")
                                for access_point in access_points
                            ]
                        }
                    },
                }
            ],
        },
        Roles=[family.iam_manager.task_role.name],
    )
    add_resource(family.template, policy)


def add_efs_definition_to_target_family(new_efs, target):
    add_parameters(
        target[0].template,
        [new_efs.attributes_outputs[FS_ARN]["ImportParameter"]],
    )
    target[0].stack.Parameters.update(
        {
            new_efs.attributes_outputs[FS_ARN][
                "ImportParameter"
            ].title: new_efs.attributes_outputs[FS_ARN]["ImportValue"]
        }
    )


def override_service_volume(new_efs, fs_id, target, access_points, volumes):
    """
    Function to override service volume if a specific definition was set for it
    """
    for service in target[2]:
        if not service.user:
            continue
        mount_points = get_service_mount_points(service)
        for count, mount_pt in enumerate(mount_points):
            if mount_pt.SourceVolume == new_efs.volume.volume_name:
                container_volume_name = (
                    f"{new_efs.volume.volume_name}{service.logical_name}"
                )
                setattr(
                    mount_pt,
                    "SourceVolume",
                    container_volume_name,
                )
                sub_service_specific_access_point = AccessPoint(
                    f"{new_efs.logical_name}{service.logical_name}ServiceEfsAccessPoint",
                    FileSystemId=Ref(fs_id),
                    PosixUser=PosixUser(
                        Uid=service.user,
                        Gid=service.group if service.group else service.user,
                    ),
                    RootDirectory=RootDirectory(
                        CreationInfo=CreationInfo(
                            OwnerUid=service.user,
                            OwnerGid=service.group if service.group else service.user,
                            Permissions=set_else_none(
                                "RootDirectoryCreateMode", new_efs.parameters, "0775"
                            ),
                        ),
                        Path=mount_pt.ContainerPath,
                    ),
                )
                add_resource(target[0].template, sub_service_specific_access_point)
                access_points.append(sub_service_specific_access_point)
                volumes.append(
                    Volume(
                        EFSVolumeConfiguration=EFSVolumeConfiguration(
                            FilesystemId=Ref(fs_id),
                            AuthorizationConfig=AuthorizationConfig(
                                AccessPointId=Ref(sub_service_specific_access_point),
                                IAM="ENABLED",
                            ),
                        ),
                        Name=container_volume_name,
                    )
                )


def set_user_to_access_points(efs, fs_id, access_points, service):
    """
    Function to set the PosixUser to a specific access point for a specific given service
    """
    group_id = service.group if service.group else service.user
    mount_points = get_service_mount_points(service)
    for mount_pt in mount_points:
        if mount_pt.SourceVolume == efs.volume.volume_name:
            for access_point in access_points:
                setattr(
                    access_point,
                    "PosixUser",
                    PosixUser(Uid=service.user, Gid=group_id),
                )
                setattr(
                    access_point,
                    "RootDirectory",
                    RootDirectory(
                        CreationInfo=CreationInfo(
                            OwnerUid=service.user,
                            OwnerGid=group_id,
                            Permissions=set_else_none(
                                "RootDirectoryCreateMode", efs.parameters, "0775"
                            ),
                        ),
                        Path=mount_pt.ContainerPath,
                    ),
                ),


def override_efs_settings(new_efs, target, fs_id_parameter, access_points, volumes):
    """
    Function to determine if access points should be set on a per service of the task definition
    and update the volumes and mount points accordingly

    :param ecs_composex.efs.efs_stack.Efs new_efs:
    :param tuple target:
    :param ecs_composex.common.cfn_params.Parameter fs_id_parameter:
    :param list access_points:
    :param list volumes:
    :return:
    """
    if [service.user for service in target[2]] and len(
        [service.user for service in target[2]]
    ) > 1:
        override_service_volume(
            new_efs, fs_id_parameter, target, access_points, volumes
        )
    elif [service.user for service in target[2]] and len(
        [service.user for service in target[2]]
    ) == 1:
        for service in target[2]:
            if service.user:
                set_user_to_access_points(
                    new_efs,
                    fs_id_parameter,
                    access_points,
                    service,
                )


def looked_up_efs_family_hook(
    efs: Efs, family: ComposeFamily, settings: ComposeXSettings
) -> None:
    sg_id = efs.add_attribute_to_another_stack(family.stack, FS_MNT_PT_SG_ID, settings)
    add_parameters(family.template, [sg_id["ImportParameter"]])
    add_security_group_ingress(
        family, efs.logical_name, Ref(sg_id["ImportParameter"]), 2049
    )
    family.stack.Parameters.update(
        {sg_id["ImportParameter"].title: sg_id["ImportValue"]}
    )


def expand_family_with_efs_volumes(
    efs_root_stack_title: str, efs: Efs, settings: ComposeXSettings
):
    """
    Function to add the EFS Volume definition to the task definition for the service to use.
    """
    fs_id_parameter = efs.attributes_outputs[FS_ID]["ImportParameter"]
    fs_id_getatt = efs.attributes_outputs[FS_ID]["ImportValue"]
    for target in efs.families_targets:
        family: ComposeFamily = target[0]
        if family.service_compute.launch_type == "EXTERNAL":
            LOG.warning(
                f"x-efs - {family.name} - When using EXTERNAL Launch Type, networking settings cannot be set."
            )
            continue
        if efs.lookup:
            looked_up_efs_family_hook(efs, family, settings)
        access_points = []
        family.stack.Parameters.update({fs_id_parameter.title: fs_id_getatt})
        add_parameters(family.template, [fs_id_parameter])
        task_definition = family.template.resources[TASK_T]
        efs_config_kwargs = {"FilesystemId": Ref(fs_id_parameter)}
        access_point_title: str = (
            f"{efs.logical_name}{family.logical_name}EfsAccessPoint"
        )
        efs_access_point = None
        if (
            efs.parameters
            and keyisset("EnforceIamAuth", efs.parameters)
            or [service.user for service in target[2]]
        ):
            add_efs_definition_to_target_family(efs, target)
            efs_access_point = add_resource(
                family.template,
                AccessPoint(
                    access_point_title,
                    FileSystemId=Ref(fs_id_parameter),
                ),
            )
        if not efs_access_point and access_point_title in family.template.resources:
            efs_access_point = family.template.resources[access_point_title]
            if efs_access_point not in access_points:
                access_points.append(efs_access_point)
        if efs_access_point:
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
            Name=efs.volume.volume_name,
        )
        volumes = get_volumes(task_definition)
        volumes.append(efs_volume_definition)
        override_efs_settings(efs, target, fs_id_parameter, access_points, volumes)
        add_task_iam_access_to_access_point(family, access_points, efs)


def efs_to_ecs(resources, services_stack, res_root_stack, settings):
    """Function to associate back the EFS FS to services."""
    for resource_name, resource in resources.items():
        LOG.info(f"{resource.module.res_key}.{resource_name} - Linking to services")
        if not resource.mappings and resource.cfn_resource:
            handle_new_tcp_resource(
                resource,
                port_parameter=FS_PORT,
                sg_parameter=FS_MNT_PT_SG_ID,
                settings=settings,
            )
            expand_family_with_efs_volumes(res_root_stack.title, resource, settings)
        else:
            expand_family_with_efs_volumes(None, resource, settings)
