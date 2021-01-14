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

"""
Package to handle recurring Secrets tasks
"""

from troposphere import Parameter
from troposphere import Ref, Sub
from troposphere.docdb import DBCluster as DocdbCluster, DBInstance as DocdbInstance
from troposphere.rds import DBCluster as RdsCluster, DBInstance as RdsInstance
from troposphere.secretsmanager import (
    Secret,
    SecretTargetAttachment,
    GenerateSecretString,
)
from ecs_composex.common import add_parameters


def add_db_secret(template, resource_title):
    """
    Function to add a Secrets Manager secret that will be associated with the DB

    :param template.Template template: The template to add the secret to.
    :param str resource_title: The Logical name of the resource associated to that secret
    """
    username = Parameter(
        f"{resource_title}Username",
        Type="String",
        MinLength=3,
        MaxLength=16,
        Default="dbadmin",
    )
    password_length = Parameter(
        f"{resource_title}PasswordLength",
        Type="Number",
        MinValue=8,
        MaxValue=32,
        Default=16,
    )
    add_parameters(template, [username, password_length])
    secret = Secret(
        f"{resource_title}Secret",
        template=template,
        GenerateSecretString=GenerateSecretString(
            SecretStringTemplate=Sub(f'{{"username":"${{{username.title}}}"}}'),
            GenerateStringKey="password",
            ExcludeCharacters="<>%`|;,.",
            ExcludePunctuation=True,
            ExcludeLowercase=False,
            ExcludeUppercase=False,
            IncludeSpace=False,
            RequireEachIncludedType=True,
            PasswordLength=Ref(password_length),
        ),
    )
    return secret


def add_db_dependency(resource, secret):
    if hasattr(resource, "DependsOn") and secret.title not in resource.DependsOn:
        resource.DependsOn.append(secret.title)
    elif not hasattr(resource, "DependsOn"):
        setattr(resource, "DependsOn", [secret.title])


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
