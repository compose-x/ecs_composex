#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Package to handle recurring Secrets tasks
"""

from troposphere import Parameter, Ref, Sub
from troposphere.docdb import DBCluster as DocdbCluster
from troposphere.docdb import DBInstance as DocdbInstance
from troposphere.rds import DBCluster as RdsCluster
from troposphere.rds import DBInstance as RdsInstance
from troposphere.secretsmanager import (
    GenerateSecretString,
    Secret,
    SecretTargetAttachment,
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
