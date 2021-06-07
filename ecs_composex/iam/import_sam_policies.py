#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to import Policies templates from AWS SAM policies templates.
"""

import json

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
