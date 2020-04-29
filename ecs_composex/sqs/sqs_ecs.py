# -*- coding: utf-8 -*-
"""
Module to apply SQS settings onto ECS Services
"""

from ecs_composex.common import LOG, KEYISSET
from ecs_composex.ecs.ecs_params import TASK_ROLE_T
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.sqs.sqs_perms import generate_sqs_permissions, generate_sqs_envvars


def apply_settings_to_service(
    service_template, service_name, perms, env_vars, access_type
):
    containers = define_service_containers(service_template)
    policy = perms[access_type]
    task_role = service_template.resources[TASK_ROLE_T]
    task_role.Policies.append(policy)
    for container in containers:
        environment = getattr(container, "Environment")
        environment += env_vars
        LOG.debug(environment)


def sqs_to_ecs(queues, services_stack, sqs_stack, **kwargs):
    """
    Function to apply SQS settings to ECS Services
    :return:
    """
    for queue_name in queues:
        queue = queues[queue_name]
        if queue_name not in sqs_stack.resources:
            raise KeyError(f"SQS queue {queue_name} not a resource of the SQS stack")
        perms = generate_sqs_permissions(queue_name, queue, **kwargs)
        envvars = generate_sqs_envvars(queue_name, queue, **kwargs)

        LOG.info(services_stack.stack_template.resources.keys())
        if perms and envvars and KEYISSET("Services", queue):
            for service in queue["Services"]:
                if service["name"] not in services_stack.stack_template.resources:
                    raise KeyError(
                        f"Service {service['name']} not in the services stack",
                        services_stack.stack_template.resources,
                    )
                service_stack = services_stack.stack_template.resources[service["name"]]
                apply_settings_to_service(
                    service_stack.stack_template,
                    service["name"],
                    perms,
                    envvars,
                    service["access"],
                )
