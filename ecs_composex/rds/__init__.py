# -*- coding: utf-8 -*-
"""
Module to handle AWS RDS CFN Templates creation
"""

import os
import boto3
from warnings import warn
from ecs_composex import XFILE_DEST
from ecs_composex.common import (
    validate_input,
    validate_kwargs,
    load_composex_file,
    LOG,
    KEYISSET,
)
from ecs_composex.rds.rds_template import generate_rds_templates

RES_KEY = f"x-{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}"
RDS_SSM_PREFIX = f"/{RES_KEY}/"


def create_rds_template(session=None, **kwargs):
    """
    Creates the CFN Troposphere template

    :param session: boto3 session to override default
    :type session: boto3.session.Session

    :return: rds_tpl
    :rtype: troposphere.Template
    """
    content = load_composex_file(kwargs[XFILE_DEST])
    if not KEYISSET(RES_KEY, content):
        warn(f"No {RES_KEY} found in the docker compose definition. Skipping")
        return None
    validate_input(content, RES_KEY)
    validate_kwargs(["BucketName"], kwargs)

    if session is None:
        session = boto3.session.Session()
    rds_tpl = generate_rds_templates(compose_content=content, session=session, **kwargs)
    LOG.debug(f"Template for {RES_KEY} validated by CFN.")
    return rds_tpl
