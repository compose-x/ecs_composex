#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to import Policies templates from AWS SAM policies templates.
"""

import json
import warnings

from importlib_resources import files as pkg_files

from ..common import setup_logging

try:
    from samtranslator.policy_templates_data import POLICY_TEMPLATES_FILE

    USE_SAM_POLICIES = True
except ImportError:
    POLICY_TEMPLATES_FILE = None
    USE_SAM_POLICIES = False
    warnings.warn("Cannot use AWS SAM Polices. aws-sam-translator is not installed.")

LOG = setup_logging()


def import_and_cleanse_policies():
    """
    Function to go over each policy defined in AWS SAM policies and align it to ECS ComposeX expected format.

    :return: The policies
    :rtype: dict
    """
    if not USE_SAM_POLICIES:
        LOG.error("Unable to load SAM Policies templates due to Library load error")
        return {}
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
