# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to import Policies templates from AWS SAM policies templates.
"""

import json

from importlib_resources import files as pkg_files


def import_and_cleanse_sam_policies():
    """
    Function to go over each policy defined in AWS SAM policies and align it to ECS ComposeX expected format.

    :return: The policies
    :rtype: dict
    """
    template_path = str(pkg_files("ecs_composex").joinpath("iam/sam_policies.json"))
    with open(template_path) as policies_fd:
        policies_orig = json.loads(policies_fd.read())["Templates"]
    import_policies = {}

    for name, value in policies_orig.items():
        import_policies[name] = {
            "Action": value["Definition"]["Statement"][0]["Action"],
            "Effect": "Allow",
            "Resource": ["${ARN}"],
        }
    return import_policies


def get_access_types(module_name: str, perms_path: str = None) -> dict:
    """
    Retrieves the Permissions definitions for a given module

    :param str module_name:
    :param str perms_path: Override path to the permissions, instead of relying on module name
    :return: the policies
    :rtype: dict
    """
    sam_policies = import_and_cleanse_sam_policies()
    if not perms_path:
        source = str(
            pkg_files("ecs_composex").joinpath(
                f"{module_name}/{module_name}_perms.json"
            )
        )
    else:
        source = perms_path
    try:
        with open(
            source,
            encoding="utf-8-sig",
        ) as perms_fd:
            dyn_policies = json.loads(perms_fd.read())
        sam_policies.update(dyn_policies)
        return sam_policies
    except OSError:
        return sam_policies
