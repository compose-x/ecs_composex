# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, FindInMap, GetAtt, ImportValue, Ref, Sub
from troposphere.ecs import ContainerDefinition, Environment

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import LOG_GROUP_RETENTION


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


def import_env_variables(environment):
    """
    Function to import Docker compose env variables into ECS Env Variables

    :param environment: Environment variables as defined on the ecs_service definition
    :type environment: dict
    :return: list of Environment
    :rtype: list<troposphere.ecs.Environment>
    """
    env_vars = []
    if isinstance(environment, list):
        for key in environment:
            if not isinstance(key, str) or key.find(r"=") < 0:
                raise TypeError(
                    f"Environment variable {key} must be a string in the Key=Value format"
                )
            splits = key.split(r"=")
            env_vars.append(Environment(Name=splits[0], Value=str(splits[1])))

    elif isinstance(environment, dict):
        for key, value in environment.items():
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


def extend_container_envvars(container: ContainerDefinition, env_vars: list) -> None:
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
    if hasattr(container, "Environment"):
        environment = getattr(container, "Environment")
        if isinstance(environment, Ref) and environment.data["Ref"] == AWS_NO_VALUE:
            environment = []
            setattr(container, "Environment", environment)
        elif not isinstance(environment, list):
            raise TypeError(
                f"container def Environment {environment} is not list or Ref(AWS_NO_VALUE).",
                type(environment),
            )
    else:
        environment = []
        setattr(container, "Environment", environment)
    existing = [
        var.Name
        for var in environment
        if isinstance(var, Environment) and isinstance(var.Name, str)
    ]
    for var in env_vars:
        if var.Name not in existing:
            LOG.debug(f"Adding {var.Name} to {existing}")
            environment.append(var)

    LOG.debug(f"{container.Name}, {[env.Name for env in environment]}")


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


def get_closest_valid_log_retention_period(set_expiry):
    return min(
        LOG_GROUP_RETENTION.AllowedValues,
        key=lambda x: abs(x - max([set_expiry])),
    )


def set_logging_expiry(service):
    """
    Method to reset the logging retention period to the closest valid value.

    :param ecs_composex.common.compose_services.ComposeService service:
    :return:
    """
    closest_valid = LOG_GROUP_RETENTION.Default
    if service.x_logging and keyisset("RetentionInDays", service.x_logging):
        set_expiry = int(service.x_logging["RetentionInDays"])
        if set_expiry not in LOG_GROUP_RETENTION.AllowedValues:
            closest_valid = get_closest_valid_log_retention_period(set_expiry)

    service.x_logging.update({"RetentionInDays": closest_valid})
    return closest_valid
