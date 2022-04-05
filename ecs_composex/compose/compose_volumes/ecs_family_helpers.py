#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import If, NoValue
from troposphere.ecs import DockerVolumeConfiguration, Host, MountPoint, Volume

from ecs_composex.common import NONALPHANUM
from ecs_composex.ecs.ecs_conditions import USE_FARGATE_CON_T


def set_services_mount_points(family):
    """
    Method to set the mount points to the Container Definition of the defined service

    if the volume["volume"] is none, this is not a shared volume, which then works only
    when not using Fargate (i.e. EC2 host/ ECS Anywhere)
    """
    for service in family.services:
        mount_points = []
        if not hasattr(service.container_definition, "MountPoints"):
            setattr(service.container_definition, "MountPoints", mount_points)
        else:
            mount_points = getattr(service.container_definition, "MountPoints")
        for volume in service.volumes:
            if keyisset("volume", volume):
                mnt_point = MountPoint(
                    ContainerPath=volume["target"],
                    ReadOnly=volume["read_only"],
                    SourceVolume=volume["volume"].volume_name,
                )
            else:
                mnt_point = If(
                    USE_FARGATE_CON_T,
                    NoValue,
                    MountPoint(
                        ContainerPath=volume["target"],
                        ReadOnly=volume["read_only"],
                        SourceVolume=NONALPHANUM.sub("", volume["target"]),
                    ),
                )
            mount_points.append(mnt_point)


def define_shared_volumes(family):
    """
    Method to create a list of shared volumes within the task family and set the volume to shared = True if not.

    :return: list of shared volumes within the task definition
    :rtype: list
    """
    family_task_volumes = []
    for service in family.services:
        for volume in service.volumes:
            if not keyisset("volume", volume):
                continue
            if volume["volume"] and volume["volume"] not in family_task_volumes:
                family_task_volumes.append(volume["volume"])
            else:
                volume["volume"].is_shared = True
    return family_task_volumes


def define_host_volumes(family):
    """
    Goes over all volumes of all services and if the volume is None, source starts with /
    then this is a host volume
    :return: list of volumes
    :rtype: list[dict]
    """
    host_volumes = []
    for service in family.services:
        for volume in service.volumes:
            if (
                (
                    (keypresent("volume", volume) and volume["volume"] is None)
                    or not keyisset("volume", volume)
                )
                and keyisset("source", volume)
                and volume["source"].startswith(r"/")
            ):
                host_volumes.append(volume)
    return host_volumes


def set_volumes(family):
    """
    Method to create the volumes definition to the Task Definition

    :return:
    """
    family_task_volumes = define_shared_volumes(family)
    host_volumes = define_host_volumes(family)
    if not hasattr(family.task_definition, "Volumes"):
        family_definition_volumes = []
        setattr(family.task_definition, "Volumes", family_definition_volumes)
    else:
        family_definition_volumes = getattr(family.task_definition, "Volumes")
    for volume in family_task_volumes:
        if volume.type == "volume" and volume.driver == "local":
            volume.cfn_volume = Volume(
                Host=NoValue,
                Name=volume.volume_name,
                DockerVolumeConfiguration=If(
                    USE_FARGATE_CON_T,
                    NoValue,
                    DockerVolumeConfiguration(
                        Scope="task" if not volume.is_shared else "shared",
                        Autoprovision=NoValue if not volume.is_shared else True,
                    ),
                ),
            )
        if volume.cfn_volume:
            family_definition_volumes.append(volume.cfn_volume)
    for volume_config in host_volumes:
        cfn_volume = If(
            USE_FARGATE_CON_T,
            NoValue,
            Volume(
                Host=Host(SourcePath=volume_config["source"]),
                DockerVolumeConfiguration=NoValue,
                Name=NONALPHANUM.sub("", volume_config["target"]),
            ),
        )
        family_definition_volumes.append(cfn_volume)
    set_services_mount_points(family)
