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
Module of functions to help with container definition
"""


from troposphere import Ref, GetAtt, ImportValue, Sub, AWS_NO_VALUE
from troposphere.ecs import ContainerDefinition, Environment, PortMapping
from ecs_composex.common import LOG


def import_env_variables(environment):
    """
    Function to import Docker compose env variables into ECS Env Variables

    :param environment: Environment variables as defined on the ecs_service definition
    :type environment: dict
    :return: list of Environment
    :rtype: list<troposphere.ecs.Environment>
    """
    env_vars = []
    for key in environment:
        if not isinstance(environment[key], str):
            env_vars.append(Environment(Name=key, Value=str(environment[key])))
        else:
            env_vars.append(Environment(Name=key, Value=environment[key]))
    return env_vars


def generate_port_mappings(ports):
    """
    Generates a port mapping from the Docker compose file.
    Given we are going to use AWS VPC mode, we are only considering the app port.

    :param ports: list of ports used by the ecs_service
    :type ports: list
    :returns: mappings, list of port mappings
    :rtype: list
    """
    mappings = []
    if not isinstance(ports, list):
        return mappings
    for port in ports:
        if not isinstance(port, dict):
            continue
        mappings.append(
            PortMapping(ContainerPort=port["target"], HostPort=port["target"])
        )
    if mappings:
        return mappings
    return Ref(AWS_NO_VALUE)


def extend_container_secrets(container, secret):
    """
    Function to add secrets to a Container definition

    :param container: container definition
    :type container: troposphere.ecs.ContainerDefinition
    :param secret: secret to add
    :type secret: troposphere.ecs.Secret
    """
    if hasattr(container, "Secrets"):
        secrets = getattr(container, "Secrets")
        if secrets:
            uniq = [secret.Name for secret in secrets]
            if secret.Name not in uniq:
                secrets.append(secret)
        else:
            setattr(container, "Secrets", [secret])
    else:
        setattr(container, "Secrets", [secret])


def extend_container_envvars(container, env_vars):
    if (
        isinstance(container, ContainerDefinition)
        and not isinstance(container.Name, (Ref, Sub, GetAtt, ImportValue))
        and container.Name.startswith("AWS")
    ):
        LOG.debug(f"Ignoring AWS Container {container.Name}")
        return
    environment = (
        getattr(container, "Environment")
        if hasattr(container, "Environment")
        and not isinstance(getattr(container, "Environment"), Ref)
        else []
    )
    if environment:
        existing = [var.Name for var in environment]
        for var in env_vars:
            if var.Name not in existing:
                LOG.debug(f"Adding {var.Name} to {existing}")
                environment.append(var)

    else:
        setattr(container, "Environment", env_vars)
    LOG.debug(environment)
