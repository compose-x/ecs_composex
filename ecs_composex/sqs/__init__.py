# -*- coding: utf-8 -*-
"""Module to handle AWS SQS CFN Templates creation"""

import os
import boto3

from ecs_composex.common import LOG
from ecs_composex.common import (
    validate_input,
    validate_kwargs,
    load_composex_file
)
from ecs_composex.common.templates import validate_template
from ecs_composex.sqs.sqs_template import generate_sqs_root_template

RES_KEY = f"x-{os.path.basename(os.path.dirname(os.path.abspath(__file__)))}"
SQS_SSM_PREFIX = f"/{RES_KEY}/"


def create_sqs_template(session=None, **kwargs):
    """
    Creates the CFN Troposphere template

    :param session: boto3 session to override default
    :type session: boto3.session.Session

    :return: sqs_tpl
    :rtype: troposphere.Template
    """
    content = load_composex_file(kwargs['ComposeXFile'])
    validate_input(content, RES_KEY)
    validate_kwargs(['BucketName'], kwargs)

    if session is None:
        session = boto3.session.Session()
    sqs_tpl = generate_sqs_root_template(compose_content=content, session=session, **kwargs)

    validate_template(sqs_tpl.to_json(), 'sqs_root')
    LOG.debug("Template for SQS validated by CFN.")
    return sqs_tpl
