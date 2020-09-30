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
