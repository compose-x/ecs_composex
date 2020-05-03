# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Module to handle AWS SQS CFN Templates creation"""

import boto3

from ecs_composex.common import validate_input, validate_kwargs, load_composex_file
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common.stacks import ComposeXStack
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


class XResource(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """
