# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to provide services with access to the RDS databases.
"""

from troposphere import Ref, GetAtt, Sub
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import Secret as EcsSecret
from troposphere.iam import PolicyType

from ecs_composex.common import keyisset
from ecs_composex.common.compose_services import extend_container_secrets
from ecs_composex.ecs.ecs_params import TASK_ROLE_T, EXEC_ROLE_T, SG_T
from ecs_composex.rds.rds_params import (
    DB_SECRET_POLICY_NAME,
)


def generate_rds_secrets_permissions(resources, db_name):
    """
    Function to generate the IAM policy to use for the ECS Execution role to get access to the RDS secrets
    :return:
    """
    return {
        "Sid": f"AccessTo{db_name}Secret",
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue", "secretsmanager:GetSecret"],
        "Resource": resources,
    }


def add_rds_policy(service_template, secret_import, db_name, use_task_role=False):
    """
    Function to add or append policy to access DB Secret for the Execution Role
    :param service_template:
    :param secret_import:
    :return:
    """
    db_policy_statement = generate_rds_secrets_permissions(secret_import, db_name)
    task_role = service_template.resources[TASK_ROLE_T]
    exec_role = service_template.resources[EXEC_ROLE_T]
    if keyisset(DB_SECRET_POLICY_NAME, service_template.resources):
        db_policy = service_template.resources[DB_SECRET_POLICY_NAME]
        db_policy.PolicyDocument["Statement"].append(db_policy_statement)
        if use_task_role:
            db_policy.Roles.append(Ref(task_role))
    else:
        policy = PolicyType(
            DB_SECRET_POLICY_NAME,
            template=service_template,
            Roles=[Ref(exec_role)],
            PolicyName=DB_SECRET_POLICY_NAME,
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [db_policy_statement],
            },
        )
        if use_task_role:
            policy.Roles.append(Ref(task_role))


def add_security_group_ingress(service_stack, db_name, sg_id, port):
    """
    Function to add a SecurityGroupIngress rule into the ECS Service template

    :param ecs_composex.ecs.ServicesStack service_stack: The root stack for the services
    :param str db_name: the name of the database to use for imports
    :param sg_id: The security group Id to use for ingress. DB Security group, not service's
    :param port: The port for Ingress to the DB.
    """
    service_template = service_stack.stack_template
    SecurityGroupIngress(
        f"AllowRdsFrom{db_name}to{service_stack.title}",
        template=service_template,
        GroupId=sg_id,
        FromPort=port,
        ToPort=port,
        Description=Sub(f"Allow FROM {db_name} TO {service_stack.title}"),
        SourceSecurityGroupId=GetAtt(service_template.resources[SG_T], "GroupId"),
        SourceSecurityGroupOwnerId=Ref("AWS::AccountId"),
        IpProtocol="6",
    )


def db_secrets_names(db):
    """
    Function to return the list of env vars set for the DB to use as env vars for the Secret.

    :return: list of names to use.
    :rtype: list
    """
    names = []
    if keyisset("EnvNames", db.settings):
        names = db.settings["EnvNames"]
    if db.name not in names:
        names.append(db.name)
    return names


def add_secret_to_container(db, secret_import, container_definition):
    """
    Function to add DB secret to container

    :param ecs_composex.common.compose_resources.Rds db: the RDS DB object
    :param container_definition: The container definition to add the secret to.
    :param str,AWSHelper secret_import: secret arn
    """

    db_secrets = [
        EcsSecret(Name=name, ValueFrom=secret_import) for name in db_secrets_names(db)
    ]
    for db_secret in db_secrets:
        extend_container_secrets(container_definition, db_secret)
