#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref
from troposphere.ecs import AuthorizationConfig, EFSVolumeConfiguration, Volume
from troposphere.efs import AccessPoint, CreationInfo, PosixUser, RootDirectory
from troposphere.iam import PolicyType

from ecs_composex.common import add_parameters
from ecs_composex.ecs.ecs_params import SERVICE_T, TASK_ROLE_T, TASK_T
from ecs_composex.efs.efs_params import FS_ARN, FS_ID, FS_MNT_PT_SG_ID, FS_PORT
from ecs_composex.tcp_resources_settings import handle_new_tcp_resource


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

    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param list<troposphere.efs.AccessPoint> access_points:
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
        Roles=[Ref(task_role)],
    )
    service_depends_on.append(policy.title)
    family.template.add_resource(policy)


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
                            Permissions="0755",
                        ),
                        Path=mount_pt.ContainerPath,
                    ),
                )
                target[0].template.add_resource(sub_service_specific_access_point)
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
                    access_point, "PosixUser", PosixUser(Uid=service.user, Gid=group_id)
                )
                setattr(
                    access_point,
                    "RootDirectory",
                    RootDirectory(
                        CreationInfo=CreationInfo(
                            OwnerUid=service.user, OwnerGid=group_id, Permissions="0755"
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
        access_points = []
        target[0].stack.Parameters.update({fs_id_parameter.title: fs_id_getatt})
        add_parameters(target[0].template, [fs_id_parameter])
        task_definition = target[0].template.resources[TASK_T]
        efs_config_kwargs = {"FilesystemId": Ref(fs_id_parameter)}
        if (
            new_efs.parameters
            and keyisset("EnforceIamAuth", new_efs.parameters)
            or [service.user for service in target[2]]
        ):
            add_efs_definition_to_target_family(new_efs, target)
            efs_access_point = target[0].template.add_resource(
                AccessPoint(
                    f"{new_efs.logical_name}{target[0].logical_name}EfsAccessPoint",
                    FileSystemId=Ref(fs_id_parameter),
                )
            )
            access_points.append(efs_access_point)
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
        volumes = get_volumes(task_definition)
        volumes.append(efs_volume_definition)
        override_efs_settings(new_efs, target, fs_id_parameter, access_points, volumes)
        add_task_iam_access_to_access_point(target[0], access_points, new_efs)


def efs_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to associate back the EFS FS to services.

    :param resources:
    :param services_stack:
    :param res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """

    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    for new_res in new_resources:
        handle_new_tcp_resource(
            new_res,
            res_root_stack,
            port_parameter=FS_PORT,
            sg_parameter=FS_MNT_PT_SG_ID,
        )
        expand_family_with_efs_volumes(res_root_stack.title, new_res, settings)
