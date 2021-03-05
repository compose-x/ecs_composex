# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only

"""
Module to deployment with compute resources
"""

from behave import given, when, then


@given("I want to use spot fleet")
def step_impl(context):
    """
    Enable to test with EC2 compute resources
    """
    context.settings.create_compute = True
