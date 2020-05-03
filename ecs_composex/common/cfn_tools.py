# -*- coding: utf-8 -*-
"""
Most commonly used functions shared across all modules.
"""

import json
from ecs_composex.common import KEYISSET, LOG


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
    for param in parameters:
        config["Parameters"].update({param["ParameterKey"]: param["ParameterValue"]})
    return config


def import_parameters_into_config_file(parameters_file, config_file):
    """
    Imports parameter file and outputs it into a CFN Template config file
    :param parameters_file: path to the parameters file
    :param config_file: path to the config file.
    :return:
    """
    with open(parameters_file, "r") as params_fd:
        parameters = json.loads(params_fd.read())
    try:
        with open(config_file, "r") as config_fd:
            try:
                config = json.loads(config_fd.read())
            except json.decoder.JSONDecodeError:
                config = {"Parameters": {}}
            if not KEYISSET("Parameters", config):
                config["Parameters"] = {}
    except FileNotFoundError:
        config = {"Parameters": {}}
    print(config)
    new_config = build_config_template_file(config, parameters)
    LOG.info(new_config)

    with open(config_file, "w") as config_fd:
        config_fd.write(json.dumps(new_config, indent=4))
