#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to import Policies templates from AWS SAM policies templates.
"""

import json

from importlib_resources import files as pkg_files
from samtranslator.policy_templates_data import POLICY_TEMPLATES_FILE


def import_and_cleanse_policies():
    """
    Function to go over each policy defined in AWS SAM policies and align it to ECS ComposeX expected format.

    :return: The policies
    :rtype: dict
    """

    with open(POLICY_TEMPLATES_FILE, "r") as policies_fd:
        policies_orig = json.loads(policies_fd.read())["Templates"]
    import_policies = {}

    for name, value in policies_orig.items():
        import_policies[name] = {
            "Action": value["Definition"]["Statement"][0]["Action"],
            "Effect": "Allow",
        }
    return import_policies


def get_access_types(module_name):

    sam_policies = import_and_cleanse_policies()
    source = pkg_files("ecs_composex").joinpath(
        f"{module_name}/{module_name}_perms.json"
    )
    with open(
        source,
        "r",
        encoding="utf-8-sig",
    ) as perms_fd:
        dyn_policies = json.loads(perms_fd.read())
    sam_policies.update(dyn_policies)
    return sam_policies
