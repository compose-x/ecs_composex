#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

import boto3
from ecs_composex.sns.sns_params import RES_KEY
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common import load_composex_file, keyisset, LOG
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.sns.sns_templates import generate_sns_templates


def create_sns_template(session=None, **kwargs):
    """
    Function to create SNS templates as part of ECS ComposeX.
    :param session:
    :param kwargs:
    :return:
    """
    if session is None:
        session = boto3.session.Session()
    content = load_composex_file(kwargs[XFILE_DEST])
    if keyisset(RES_KEY, content):
        LOG.debug(f"Processing {RES_KEY} package")
        generate_sns_templates(content, **kwargs)


class XResource(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def add_sqs_stack(self):
        """
        Method to add a dependency on the SQS stacks
        """
        self.DependsOn.append("sqs")
