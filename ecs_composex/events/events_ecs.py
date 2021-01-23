#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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


from troposphere import Ref, Sub, GetAtt
from troposphere import (
    AWS_REGION,
    AWS_PARTITION,
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_URL_SUFFIX,
)
from troposphere import Parameter

from troposphere.events import (
    Target,
    EcsParameters,
    NetworkConfiguration,
    AwsVpcConfiguration,
)

from troposphere.iam import Role, Policy, PolicyType

from ecs_composex.common import add_parameters, keyisset, LOG
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME,
    FARGATE_VERSION,
    TASK_T,
    SERVICE_T,
    TASK_ROLE_T,
    EXEC_ROLE_T,
    SERVICE_SCALING_TARGET,
)
from ecs_composex.vpc.vpc_params import APP_SUBNETS, SG_ID_TYPE, SUBNETS_TYPE


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
                    service[0].logical_name, f"Outputs.{service[0].logical_name}GroupId"
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
            and SERVICE_SCALING_TARGET not in service[0].template.resources
        ):
            LOG.info(
                f"Deleting ECS Service definition from stack for {service[0].name}"
            )
            del service[0].template.resources[SERVICE_T]
        elif SERVICE_SCALING_TARGET in service[0].template.resources:
            LOG.warning(
                f"Target for event {rule.logical_name} has others dependencies. Not altering"
            )


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
