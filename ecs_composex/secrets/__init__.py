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

"""
Package to handle recurring Secrets tasks
"""

from troposphere import Ref, Sub
from troposphere.secretsmanager import (
    Secret,
    SecretTargetAttachment,
    GenerateSecretString,
)
from troposphere.rds import DBCluster as RdsCluster, DBInstance as RdsInstance
from troposphere.docdb import DBCluster as DocdbCluster, DBInstance as DocdbInstance

from ecs_composex.common import add_parameters
from ecs_composex.secrets.secrets_params import USERNAME, PASSWORD_LENGTH


def add_db_secret(template, resource_title):
    """
    Function to add a Secrets Manager secret that will be associated with the DB
    :param template.Template template: The template to add the secret to.
    """
    add_parameters(template, [USERNAME, PASSWORD_LENGTH])
    secret = Secret(
        f"{resource_title}Secret",
        template=template,
        GenerateSecretString=GenerateSecretString(
            SecretStringTemplate=Sub(f'{{"username":"${{{USERNAME.title}}}"}}'),
            GenerateStringKey="password",
            ExcludeCharacters="<>%`|;,.",
            ExcludePunctuation=True,
            ExcludeLowercase=False,
            ExcludeUppercase=False,
            IncludeSpace=False,
            RequireEachIncludedType=True,
            PasswordLength=Ref(PASSWORD_LENGTH),
        ),
    )
    return secret


def attach_to_secret_to_resource(template, resource, secret):
    """
    Function to associate a secret to a resource
    :param troposphere.Template template:
    :param resource: The resource we can link the secret to.
    :param secret: The secret to attach to the resource
    :return:
    """
    if not isinstance(resource, (RdsCluster, RdsInstance, DocdbCluster, DocdbInstance)):
        raise TypeError(
            "The resource to attach can only be one of ",
            (RdsCluster, RdsInstance, DocdbCluster, DocdbInstance),
            "Got",
            type(resource),
        )
    SecretTargetAttachment(
        f"{resource.title}SecretAttachment",
        template=template,
        DependsOn=[resource.title, secret.title],
        TargetType=resource.resource_type,
        SecretId=Ref(secret),
        TargetId=Ref(resource),
    )
