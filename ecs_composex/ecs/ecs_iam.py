#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from ecs_composex.ecs.ecs_params import TASK_T


def define_service_containers(service_template):
    """Function to set the containers list from the service_task definition object

    :param service_template: the task definition
    :type service_template: troposphere.Template

    :return: list of containers
    :rtype: list
    """
    service_task = None
    if TASK_T in service_template.resources:
        service_task = service_template.resources[TASK_T]
    try:
        if service_task:
            containers = getattr(service_task, "ContainerDefinitions")
        else:
            containers = []
    except AttributeError:
        raise ValueError(
            "Service Task definition defined but no ContainerDefinitions found"
        )
    return containers
