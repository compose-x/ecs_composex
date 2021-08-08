#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    AWS_URL_SUFFIX,
    GetAtt,
    Ref,
    Sub,
)
from troposphere.applicationautoscaling import ScalingPolicy
from troposphere.events import (
    AwsVpcConfiguration,
    EcsParameters,
    NetworkConfiguration,
    Target,
)
from troposphere.iam import Policy, PolicyType, Role

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME,
    EXEC_ROLE_T,
    FARGATE_VERSION,
    SERVICE_SCALING_TARGET,
    SERVICE_T,
    TASK_ROLE_T,
    TASK_T,
)
from ecs_composex.vpc.vpc_params import APP_SUBNETS, SG_ID_TYPE, SUBNETS_TYPE


def delete_service_from_template(service):
    """
    Function to delete the ECS Service definition and scaling related resources from the template

    :param tuple service:
    """
    del service[0].template.resources[SERVICE_SCALING_TARGET]
    stack_resources = list(service[0].template.resources.values())
    for resource in stack_resources:
        if issubclass(type(resource), ScalingPolicy):
            del service[0].template.resources[resource.title]
    outputs = list(service[0].template.outputs.keys())
    for output_name in outputs:
        if output_name.find(SERVICE_SCALING_TARGET) > 0:
            del service[0].template.outputs[output_name]


def define_service_targets(settings, stack, rule, cluster_arn):
    """
    Function to define the targets for service.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param ecs_composex.events.events_stack.XStack stack:
    :param ecs_composex.events.events_stack.Rule rule:
    :param troposphere.Sub cluster_arn:
    :return:
    """
    for service in rule.families_targets:
        service_sg_param = Parameter(
            f"{service[0].logical_name}GroupId", Type=SG_ID_TYPE
        )
        service_task_def_param = Parameter(
            f"{service[0].logical_name}{TASK_T}", Type="String"
        )
        service_subnets_param = Parameter(
            f"{service[0].logical_name}{APP_SUBNETS.title}", Type=SUBNETS_TYPE
        )
        events_policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["ecs:RunTask"],
                    "Resource": [Ref(service_task_def_param)],
                    "Condition": {"ArnLike": {"ecs:cluster": cluster_arn}},
                },
                {
                    "Effect": "Allow",
                    "Action": "iam:PassRole",
                    "Resource": ["*"],
                    "Condition": {
                        "StringLike": {
                            "iam:PassedToService": Sub(
                                f"ecs-tasks.${{{AWS_URL_SUFFIX}}}"
                            )
                        }
                    },
                },
            ],
        }
        task_events_policy_doc = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["ecs:RunTask"],
                    "Resource": [Ref(service[0].template.resources[TASK_T])],
                    "Condition": {"ArnLike": {"ecs:cluster": cluster_arn}},
                },
                {
                    "Effect": "Allow",
                    "Action": "iam:PassRole",
                    "Resource": ["*"],
                    "Condition": {
                        "StringLike": {
                            "iam:PassedToService": Sub(
                                f"ecs-tasks.${{{AWS_URL_SUFFIX}}}"
                            )
                        }
                    },
                },
            ],
        }
        events_policy = Policy(
            PolicyName="EventsAccess", PolicyDocument=events_policy_doc
        )
        service[0].template.add_resource(
            PolicyType(
                "EventsAccessPolicy",
                PolicyName="EventsAccess",
                PolicyDocument=task_events_policy_doc,
                Roles=[
                    Ref(service[0].template.resources[TASK_ROLE_T]),
                    Ref(service[0].template.resources[EXEC_ROLE_T]),
                ],
            )
        )
        role = stack.stack_template.add_resource(
            Role(
                f"{rule.logical_name}IamRoleToTrigger{service[0].logical_name}",
                AssumeRolePolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "TrustPolicy",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": Sub(f"events.${{{AWS_URL_SUFFIX}}}")
                            },
                            "Action": "sts:AssumeRole",
                        }
                    ],
                },
                ManagedPolicyArns=[],
                Policies=[events_policy],
                PermissionsBoundary=Ref(AWS_NO_VALUE),
            )
        )
        if service[0].iam and keyisset("PermissionsBoundary", service[0].iam):
            role.PermissionsBoundary = service[0].iam["PermissionsBoundary"]
        add_parameters(
            stack.stack_template,
            [service_sg_param, service_task_def_param, service_subnets_param],
        )
        stack.Parameters.update(
            {
                service_sg_param.title: GetAtt(
                    service[0].logical_name,
                    f"Outputs.{service[0].logical_name}GroupId",
                ),
                service_task_def_param.title: GetAtt(
                    service[0].logical_name,
                    f"Outputs.{service[0].logical_name}{TASK_T}",
                ),
                service_subnets_param.title: GetAtt(
                    service[0].logical_name,
                    f"Outputs.{service[0].logical_name}{APP_SUBNETS.title}",
                ),
            }
        )
        target = Target(
            EcsParameters=EcsParameters(
                NetworkConfiguration=NetworkConfiguration(
                    AwsVpcConfiguration=AwsVpcConfiguration(
                        Subnets=Ref(service_subnets_param),
                        SecurityGroups=[Ref(service_sg_param)],
                    )
                ),
                PlatformVersion=Ref(FARGATE_VERSION),
                TaskCount=service[3],
                TaskDefinitionArn=Ref(service_task_def_param),
                LaunchType="FARGATE",
            ),
            Arn=cluster_arn,
            Id=service[0].logical_name,
            RoleArn=GetAtt(role, "Arn"),
        )
        rule.cfn_resource.Targets.append(target)
        if service[0].logical_name not in stack.DependsOn:
            stack.DependsOn.append(service[0].logical_name)
        if (
            keyisset("DeleteDefaultService", service[4])
            and SERVICE_T in service[0].template.resources
        ):
            LOG.info(
                f"Deleting ECS Service definition from stack for {service[0].name}"
            )
            del service[0].template.resources[SERVICE_T]
        if SERVICE_SCALING_TARGET in service[0].template.resources:
            LOG.warning(
                f"Target for event {rule.logical_name} also had scaling rules. Deleting"
            )
            delete_service_from_template(service)


def events_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to map services to event rules
    :param resources:
    :param services_stack:
    :param res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    cluster_arn = Sub(
        f"arn:${{{AWS_PARTITION}}}:ecs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
        f"cluster/${{{CLUSTER_NAME.title}}}"
    )
    rules = [
        resources[res_name]
        for res_name in resources
        if resources[res_name].properties and not resources[res_name].lookup
    ]
    for rule in rules:
        if rule.families_targets:
            define_service_targets(settings, res_root_stack, rule, cluster_arn)
