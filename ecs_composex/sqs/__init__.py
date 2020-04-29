# -*- coding: utf-8 -*-
"""Module to handle AWS SQS CFN Templates creation"""

import boto3

from ecs_composex import XFILE_DEST
from ecs_composex.common import validate_input, validate_kwargs, load_composex_file
from ecs_composex.sqs.sqs_params import RES_KEY
from ecs_composex.sqs.sqs_template import generate_sqs_root_template


def create_sqs_template(content=None, session=None, **kwargs):
    """
    Creates the CFN Troposphere template
    :param content: docker compose file content
    :param session: boto3 session to override default
    :type session: boto3.session.Session

    :return: sqs_tpl
    :rtype: troposphere.Template
    """
    if content is None:
        content = load_composex_file(kwargs[XFILE_DEST])
    validate_input(content, RES_KEY)
    validate_kwargs(["BucketName"], kwargs)

    if session is None:
        session = boto3.session.Session()
    sqs_tpl = generate_sqs_root_template(
        compose_content=content, session=session, **kwargs
    )
    return sqs_tpl
