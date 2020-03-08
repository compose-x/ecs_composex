# -*- coding: utf-8 -*-
"""
Functions to format CFN template Outputs
"""

from troposphere import Output, Export, Sub, If
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common.cfn_conditions import USE_STACK_NAME_CON_T


def cfn_resource_type(object_name, strip=True):
    """Returns the Resource Type property removing the AWS:: prefix

    :returns: res_type
    :rtype: str
    """
    res_type = object_name.resource_type.replace(':', '')
    if strip:
        return res_type.replace('AWS', '')
    return res_type


def formatted_outputs(comments, export=False, prefix=None, use_root_stack=False):
    """Function to format the outputs easily and add exports based on a prefix

    :param comments: List of KeyPair values representing the output
    :type comments: list
    :param export: Whether or not this output should export to CFN Exports. Default: False
    :type export: bool
    :param prefix: prefix for the cfn exports. Must enable uniqueness of the output in CFN
    :type prefix: str
    :param use_root_stack: Whether this output for prefix should use the RootStackName as prefix
    :type use_root_stack: bool

    :return: outputs
    :rtype: list
    """
    outputs = []
    if isinstance(comments, list):
        for comment in comments:
            if isinstance(comment, dict):
                keys = list(comment.keys())
                args = {
                    'title': keys[0],
                    'Value': comment[keys[0]]
                }
                if export:
                    if prefix is None:
                        args['Export'] = Export(
                            If(
                                USE_STACK_NAME_CON_T,
                                Sub(f'${{AWS::StackName}}-{keys[0]}'),
                                Sub(f"${{{ROOT_STACK_NAME_T}}}-{keys[0]}")
                            )
                        )
                    elif use_root_stack:
                        Export(Sub(f'${{{ROOT_STACK_NAME_T}}}-{keys[0]}'))
                    elif isinstance(prefix, str):
                        args['Export'] = Export(Sub(f'{prefix}-{keys[0]}'))
                outputs.append(Output(**args))
    return outputs
