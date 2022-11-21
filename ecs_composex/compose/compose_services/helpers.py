# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, GetAtt, ImportValue, NoValue, Ref, Sub
from troposphere.ecs import ContainerDefinition, Environment

from ecs_composex.common.logging import LOG


def import_secrets(template, service, container, settings):
    """
    Function to import secrets from compose-x mapping to AWS Secrets in Secrets Manager

    :param troposphere.Template template:
    :param troposhere.ecs.ContainerDefinition container:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if not service.secrets:
        return
    if not keyisset("secrets", settings.compose_content):
        return
    else:
        settings_secrets = settings.compose_content["secrets"]
    for secret in service.secrets:
        if (
            isinstance(secret, str)
            and secret in settings_secrets
            and keyisset("ComposeSecret", settings_secrets[secret])
        ):
            settings_secrets[secret]["ComposeSecret"].assign_to_task_definition(
                template, container
            )
        elif isinstance(secret, dict) and keyisset("source", secret):
            secret_name = secret["source"]
            if keyisset("ComposeSecret", settings_secrets[secret_name]):
                settings_secrets[secret_name][
                    "ComposeSecret"
                ].assign_to_task_definition(template, container)


def define_string_interpolation(var_value):
    """
    Function to determine whether an env variable string should use Sub.

    :param str var_value: The env var string as defined in compose file
    :return: String as is or Sub for interpolation
    :rtype: str
    """
    if var_value.find(r"${AWS::") >= 0:
        LOG.debug(var_value)
        return Sub(var_value)
    return var_value


def set_environment_dict_from_list(environment: list) -> dict:
    """
    Transforms a list of string with a ``key=value`` into a dict of key/value

    :param list environment:
    :rtype: dict
    :return: dict of key/value
    """
    env_vars_to_map = {}
    for key in environment:
        if not isinstance(key, str) or key.find(r"=") < 0:
            raise TypeError(
                f"Environment variable {key} must be a string in the Key=Value format"
            )
        splits = key.split(r"=")
        if splits[0] not in env_vars_to_map:
            env_vars_to_map[splits[0]] = splits[1]
        else:
            LOG.warning(f"{splits[0]} was already defined. Overriding to newer value")
            env_vars_to_map[splits[0]] = splits[1]
    return env_vars_to_map


def import_env_variables(environment) -> list:
    """
    Function to import Docker compose env variables into ECS Env Variables

    :param environment: Environment variables as defined on the ecs_service definition
    :type environment: dict
    :return: list of Environment
    :rtype: list<troposphere.ecs.Environment>
    """
    env_vars = []
    if isinstance(environment, list):
        env_vars_to_map = set_environment_dict_from_list(environment)

    elif isinstance(environment, dict):
        env_vars_to_map = environment
    else:
        raise TypeError(
            "Enviroment must be a list of string or a dict of key/value where value is a string"
        )
    for key, value in env_vars_to_map.items():
        if not isinstance(value, str):
            env_vars.append(Environment(Name=key, Value=str(environment[key])))
        else:
            env_vars.append(
                Environment(
                    Name=key,
                    Value=define_string_interpolation(value),
                )
            )
    return env_vars


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


def set_validate_environment(container: ContainerDefinition) -> None:
    """
    Validates that the environment property of the container definition is valid.
    If is NoValue
    """
    _environment = getattr(container, "Environment")
    if isinstance(_environment, Ref) and _environment == NoValue:
        setattr(container, "Environment", [])
    elif not isinstance(_environment, list):
        raise TypeError(
            f"container def Environment {_environment} is not list or Ref(AWS_NO_VALUE).",
            _environment,
        )


def extend_container_envvars(
    container: ContainerDefinition, env_vars: list, replace: bool = False
) -> None:
    """
    Extends the container environment variables with new ones to add. If not already set, defines.

    :param troposphere.ecs.ContainerDefinition container:
    :param list[troposphere.ecs.Environment] env_vars:
    :return:
    """
    ignored_containers = ["xray-daemon", "envoy", "cw_agent"]
    if (
        isinstance(container, ContainerDefinition)
        and not isinstance(container.Name, (Ref, Sub, GetAtt, ImportValue, FindInMap))
        and container.Name in ignored_containers
    ):
        LOG.debug(f"Ignoring AWS Container {container.Name}")
        return
    if not hasattr(container, "Environment"):
        setattr(container, "Environment", [])
    set_validate_environment(container)
    environment = getattr(container, "Environment")
    existing_names = [
        var.Name
        for var in environment
        if isinstance(var, Environment) and isinstance(var.Name, str)
    ]
    for var in env_vars:
        if not isinstance(var, Environment):
            if var not in environment:
                LOG.debug(f"var already exists {var}")
            else:
                environment.append(var)
            continue

        if var.Name not in existing_names:
            LOG.debug(f"Adding {var.Name} to {existing_names}")
            environment.append(var)
        elif var.Name in existing_names and replace:
            for defined_env_var in environment:
                if defined_env_var.Name == var.Name:
                    setattr(defined_env_var, "Value", var.Value)
                    break

    LOG.debug(
        f"{container.Name}, {[env.Name for env in environment if isinstance(env, Environment)]}"
    )


def define_ingress_mappings(service_ports):
    """
    Function to create a mapping of sources for a common target
    """
    udp_mappings = {}
    tcp_mappings = {}
    ports_mappings = {"tcp": tcp_mappings, "udp": udp_mappings}
    for port in service_ports:
        if not keyisset("target", port):
            raise KeyError("The ports must always at least define the target.")
        if keyisset("protocol", port) and port["protocol"] == "udp":
            mappings = udp_mappings
        else:
            mappings = tcp_mappings

        if not port["target"] in mappings.keys() and keyisset("published", port):
            mappings[port["target"]] = [port["published"]]

        elif not port["target"] in mappings.keys() and not keyisset("published", port):
            mappings[port["target"]] = []
        elif (
            port["target"] in mappings.keys()
            and not port["published"] in mappings[port["target"]]
        ):
            mappings[port["target"]].append(port["published"])
    return ports_mappings


def validate_healthcheck(healthcheck, valid_keys, required_keys):
    """
    Healthcheck definition validation

    :param dict healthcheck:
    :param list valid_keys:
    :param list required_keys:
    """
    for key in healthcheck.keys():
        if key not in valid_keys:
            raise AttributeError(f"Key {key} is not valid. Expected", valid_keys)
    if not all(required_keys) not in healthcheck.keys():
        raise AttributeError(
            f"Expected at least {required_keys}. Got", healthcheck.keys()
        )
