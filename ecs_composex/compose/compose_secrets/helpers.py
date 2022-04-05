#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Represent a service from the docker-compose services
"""

from compose_x_common.compose_x_common import keyisset


def to_java_properties(name):
    """
    Replaces `.` with `_` and set all cases to upper

    :param str name:
    :return: transformed test
    :rtype: str
    """
    return name.upper().replace(".", "_")


def to_title(name):
    """
    Function to title the name

    :param str name:
    :return:
    """

    return name.title()


def to_capitalize(name):
    """
    Function to capitalize/upper all letters and leave the rest empty

    :param name:
    :return:
    """
    return name.upper()


def define_env_var_name(secret_key):
    """
    Function to determine what the VarName key for secret will be

    :param dict secret_key: Key definition as defined in compose file
    :return: VarName value
    :rtype: str
    """
    transforms = [
        ("java_properties", to_java_properties),
        ("title", to_title),
        ("capitalize", to_capitalize),
    ]
    if keyisset("VarName", secret_key):
        return secret_key["VarName"]
    elif keyisset("Transform", secret_key) and secret_key["Transform"] in [
        t[0] for t in transforms
    ]:
        for trans in transforms:
            if trans[0] == secret_key["Transform"] and trans[1]:
                return trans[1](secret_key["SecretKey"])
    else:
        return secret_key["SecretKey"]
