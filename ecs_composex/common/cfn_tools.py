# -*- coding: utf-8 -*-
"""
Most commonly used functions shared across all modules.
"""

import json
from ecs_composex.common import KEYISSET


def build_config_template_file(parameters=None, tags=None, stack_policies=None):
    """
    Function to create the CFN Template configuration file.
    See `Documentation <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/continuous-delivery-codepipeline-cfn-artifacts.html>`_
    :param parameters: list of parameters and the value we want for it.
    :type parameters: list
    :param tags: To implement
    :param stack_policies: To implement
    """
    config = {
        'Parameters': {}
    }
    if parameters is not None and not isinstance(parameters, list):
        raise TypeError('parameters must be a list of objects', list)
    for param in parameters:
        config['Parameters'].update({param['ParameterKey']:  param['ParameterValue']})
    return config


def write_config_template_file(config, output_file):
    """
    Function to write the
    :param config:
    :param output_file:
    """
    with open(output_file, 'w') as config_fd:
        config_fd.write(json.dumps(config, indent=4))


def import_parameters_into_config_file(parameters_file, config_file):
    """
    Imports parameter file and outputs it into a CFN Template config file
    :param parameters_file: path to the parameters file
    :param config_file: path to the config file.
    :return:
    """
    with open(parameters_file, 'r') as params_fd:
        parameters = json.loads(params_fd.read())
    with open(config_file, 'r') as config_fd:
        config = json.loads(config_fd.read())
    new_params_config = build_config_template_file(parameters)
    if KEYISSET('Parameters', config):
        for param in config['Parameters']:
            if param in new_params_config['Parmeters']:
                config['Parameters'][param] = new_params_config['Parameters'][param]

    with open(config_file, 'w') as config_fd:
        config_fd.write(json.dumps(config, indent=4))
