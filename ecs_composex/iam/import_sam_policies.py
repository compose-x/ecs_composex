#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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
