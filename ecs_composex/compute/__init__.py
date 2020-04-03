# -*- coding: utf-8 -*-

"""
Module to create the compute resources, if so chosen, the SpotFleet / OnDemand instances to go with it.

The SpotFleet and OnDemand instances are optional, but the LaunchTemplate gets created so that if
for testing one would wish to run a new EC2 instance, you can simply do it from the launch template.
"""

import boto3

from ecs_composex import XFILE_DEST
from ecs_composex.common import KEYISSET, load_composex_file, build_default_stack_parameters
from ecs_composex.common.aws import get_curated_azs
from ecs_composex.common.tagging import generate_tags_parameters
from ecs_composex.compute.compute_template import generate_compute_template


def create_compute_stack(session=None, **kwargs):
    """
    Function entrypoint for CLI.
    :param session: boto3 session to override API calls with
    :type session: boto3.session.Session

    :return: cluster template
    :rtype: troposphere.Template
    """
    tags_params = ()
    stack_params = []
    compose_content = None
    if KEYISSET(XFILE_DEST, kwargs):
        compose_content = load_composex_file(kwargs[XFILE_DEST])
        tags_params = generate_tags_parameters(compose_content)
    if not KEYISSET("AwsAzs", kwargs):
        if KEYISSET("AwsRegion", kwargs):
            azs = get_curated_azs(region=kwargs["AwsRegion"])
        elif session is None:
            session = boto3.session.Session()
            azs = get_curated_azs(session=session)
        else:
            azs = get_curated_azs()
    else:
        azs = kwargs["AwsAzs"]
    template = generate_compute_template(azs, compose_content, tags_params, **kwargs)
    build_default_stack_parameters(stack_params, **kwargs)
    return template, stack_params
