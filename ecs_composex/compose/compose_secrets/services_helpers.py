#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG

from . import ComposeSecret


def match_secrets_services_config(service, s_secret, secrets):
    """
    Function to match the services and secrets
    :param service:
    :param s_secret:
    :param secrets:
    :return:
    """
    if isinstance(s_secret, str):
        secret_name = s_secret
    elif isinstance(s_secret, dict) and keyisset("source", s_secret):
        secret_name = s_secret["source"]
    else:
        raise LookupError("Could not identify the secret source", s_secret)
    for gl_secret in secrets:
        if gl_secret.name == secret_name:
            LOG.info(f"secrets.{gl_secret.name} - Mapped to {service.name}")
            service.secrets.append(gl_secret)
            gl_secret.services.append(service)


def map_secrets(service, secrets: list) -> None:
    """
    Map compose defined secret to service

    :param service:
    :param list secrets:
    """
    if keyisset(ComposeSecret.main_key, service.definition) and secrets:
        for s_secret in service.definition[ComposeSecret.main_key]:
            match_secrets_services_config(service, s_secret, secrets)
