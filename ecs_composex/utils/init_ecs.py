#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to initialize the AWS Account.
"""

from ecs_composex.common import LOG


def set_ecs_settings(session):
    """
    Function to set the ECS Account settings
    """
    ecs_settings = [
        "awsvpcTrunking",
        "serviceLongArnFormat",
        "taskLongArnFormat",
        "containerInstanceLongArnFormat",
        "containerInsights",
    ]
    client = session.client("ecs")
    for setting in ecs_settings:
        try:
            client.put_account_setting_default(name=setting, value="enabled")
            LOG.info(f"ECS Setting {setting} set to 'enabled'")
        except client.exceptions.ClientException as error:
            LOG.error(f"Failed to set {setting}")
            LOG.error(error)
