# -*- coding: utf-8 -*-
""" IAM Building block for ECS """


from troposphere import Sub, Ref
from troposphere.iam import Role, PolicyType

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import SERVICE_NAME_T, CLUSTER_NAME_T, EXEC_ROLE_T, TASK_ROLE_T, TASK_T
from ecs_composex.ecs_composex import generate_x_resource_configs
from ecs_composex.iam import service_role_trust_policy


def add_service_roles(template):
    """
    Function to create the IAM roles for the ECS task

    :param template: service template to add the resources to
    :type template: troposphere.Template
    """
    execution_role = Role(
        EXEC_ROLE_T,
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy('ecs-tasks'),
        Description=Sub(f"Execution role for ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}")
    )
    PolicyType(
        f'{EXEC_ROLE_T}Policy',
        template=template,
        PolicyName=Sub(f'EcsExecRole'),
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowsForEcrPullFromEcsAgent",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:GetRepositoryPolicy",
                        "ecr:DescribeRepositories",
                        "ecr:ListImages",
                        "ecr:DescribeImages",
                        "ecr:BatchGetImage"
                    ],
                    "Resource": ['*']
                },
                {
                    "Sid": "AllowEcsAgentOrientedTasks",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:DiscoverPollEndpoint",
                        "ecs:Poll",
                        "ecs:Submit*",
                    ],
                    "Resource": ["*"]
                },
                {
                    "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": [
                        Sub(
                            'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:'
                            f'${{{CLUSTER_NAME_T}}}:*'
                        )
                    ]
                },
                {
                    "Sid": "AllowsEcsAgentToPerformActionsForMicroservice",
                    "Effect": "Allow",
                    "Action": [
                        "ec2:AttachNetworkInterface",
                        "ec2:CreateNetworkInterface",
                        "ec2:CreateNetworkInterfacePermission",
                        "ec2:DeleteNetworkInterface",
                        "ec2:DeleteNetworkInterfacePermission",
                        "ec2:Describe*",
                        "ec2:DetachNetworkInterface",
                        "elasticloadbalancing:DeregisterInstancesFromLoadBalancer",
                        "elasticloadbalancing:DeregisterTargets",
                        "elasticloadbalancing:Describe*",
                        "elasticloadbalancing:RegisterInstancesWithLoadBalancer",
                        "elasticloadbalancing:RegisterTargets",
                    ],
                    "Resource": ["*"]
                }
            ]
        },
        Roles=[Ref(execution_role)]
    )
    Role(
        TASK_ROLE_T,
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy('ecs-tasks'),
        Description=Sub(f"TaskRole - ${{{SERVICE_NAME_T}}} in ${{{CLUSTER_NAME_T}}}"),
        ManagedPolicyArns=[],
        Policies=[]
    )


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
            containers = getattr(service_task, 'ContainerDefinitions')
        else:
            containers = []
    except AttributeError:
        raise ValueError('Service Task definition defined but no ContainerDefinitions found')
    return containers


def set_resource_type_settings(service_template, service_name, resources_permissions, env_vars, containers):
    """Function to add the resource type settings for a service if applicable

    :param service_template: the service template
    :type service_template: troposphere.Template
    :param service_name: name of the service as defined in the docker compose file
    :type service_name: str
    :param resources_permissions: resource permissions for a given resource type
    :type resources_permissions: dict
    :param env_vars: environment variables to get from the extra resources to add to the container environment
    :type env_vars: dict
    :param containers: list of containers from the task definition
    :type containers: list<troposphere.ecs.ContainerDefinition>
   """
    task_role = service_template.resources[TASK_ROLE_T]
    for resource_name in resources_permissions:
        res_vars = env_vars[resource_name]
        for permission_type in resources_permissions[resource_name]:
            permission = resources_permissions[resource_name][permission_type]
            if service_name in permission['Services']:
                task_role.Policies.append(permission['Policy'])
                for container in containers:
                    environment = getattr(container, 'Environment')
                    environment += res_vars
                    LOG.debug(environment)


def assign_x_resources_to_service(compose_content, service_name, service_tpl, **kwargs):
    """
    Parses each X component and if the service is listed there, assigns the policy to
    the service task role

    :param compose_content: docker ComposeX file content
    :type compose_content: dict
    :param service_name: name of the service
    :type service_name: str
    :param service_tpl: service template to add the resources to
    :type service_tpl: troposphere.Template
    :param kwargs: optional arguments
    :type kwargs: dict
    """
    x_resources_configs = generate_x_resource_configs(
        compose_content, **kwargs
    )
    containers = define_service_containers(service_tpl)

    for resource_type in x_resources_configs:
        if not (resource_type == 'x-rds' or resource_type == 'x-cluster'):
            resources_perms = x_resources_configs[resource_type]['permissions']
            env_vars = x_resources_configs[resource_type]['envvars']
            set_resource_type_settings(service_tpl, service_name, resources_perms, env_vars, containers)
