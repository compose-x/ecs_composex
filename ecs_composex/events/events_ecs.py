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


from troposphere import Ref, Sub, GetAtt
from troposphere import AWS_REGION, AWS_PARTITION, AWS_ACCOUNT_ID
from troposphere import Parameter

from troposphere.events import (
    Target,
    EcsParameters,
    NetworkConfiguration,
    AwsVpcConfiguration,
)

from ecs_composex.common import add_parameters, keyisset, LOG
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, FARGATE_VERSION, TASK_T, SERVICE_T
from ecs_composex.vpc.vpc_params import APP_SUBNETS, SG_ID_TYPE


def define_service_targets(stack, rule, cluster_arn):
    """
    Function to define the targets for service.

    :param ecs_composex.events.events_stack.XStack stack:
    :param ecs_composex.events.events_stack.Rule rule:
    :param troposphere.Sub cluster_arn:
    :return:
    """
    for service in rule.families_targets:
        service_sg_param = Parameter(f"{service[0].logical_name}SgId", Type=SG_ID_TYPE)
        service_task_def_param = Parameter(
            f"{service[0].logical_name}TaskDefinition", Type="String"
        )
        add_parameters(stack.stack_template, [service_sg_param, service_task_def_param])
        stack.Parameters.update(
            {
                service_sg_param.title: GetAtt(
                    service[0].logical_name, f"Outputs.ServiceGroupId"
                ),
                service_task_def_param.title: GetAtt(
                    service[0].logical_name, f"Outputs.{TASK_T}"
                ),
            }
        )
        target = Target(
            EcsParameters=EcsParameters(
                NetworkConfiguration=NetworkConfiguration(
                    AwsVpcConfiguration=AwsVpcConfiguration(
                        Subnets=Ref(APP_SUBNETS), SecurityGroups=Ref(service_sg_param)
                    )
                ),
                PlatformVersion=Ref(FARGATE_VERSION),
                TaskCount=service[3],
                TaskDefinitionArn=Ref(service_task_def_param),
            ),
            Arn=cluster_arn,
            Id=service[0].logical_name,
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


def events_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to map services to event rules
    :param resources:
    :param services_stack:
    :param res_root_stack:
    :param settings:
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
            define_service_targets(res_root_stack, rule, cluster_arn)
