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
Most commonly used functions shared across all modules.
"""

import json
from ecs_composex.common import keyisset, LOG


def build_config_template_file(config, parameters=None, tags=None, stack_policies=None):
    """
    Function to create the CFN Template configuration file.

    :param config: CFN stack config definition
    :type config: dict
    :param parameters: list of parameters and the value we want for it.
    :type parameters: list
    :param tags: To implement
    :param stack_policies: To implement
    """
    if parameters is not None and not isinstance(parameters, list):
        raise TypeError("parameters must be a list of objects", list)
    if not keyisset("Parameters", config):
        config["Parameters"] = {}
    for param in parameters:
        config["Parameters"].update({param["ParameterKey"]: param["ParameterValue"]})
    return config


def import_parameters_into_config_file(parameters_file, config_file):
    """
    Imports parameter file and outputs it into a CFN Template config file

    :param parameters_file: path to the parameters file
    :type parameters_file: str
    :param config_file: path to the config file.
    :type config_file: str
    """
    with open(parameters_file, "r") as params_fd:
        parameters = json.loads(params_fd.read())
    try:
        with open(config_file, "r") as config_fd:
            try:
                config = json.loads(config_fd.read())
            except json.decoder.JSONDecodeError:
                config = {"Parameters": {}}
            if not keyisset("Parameters", config):
                config["Parameters"] = {}
    except FileNotFoundError:
        config = {"Parameters": {}}
    print(config)
    new_config = build_config_template_file(config, parameters)
    LOG.info(new_config)

    with open(config_file, "w") as config_fd:
        config_fd.write(json.dumps(new_config, indent=4))
