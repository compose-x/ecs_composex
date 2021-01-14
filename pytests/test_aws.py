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

from os import path

import boto3
import placebo

from ecs_composex.utils.init_ecs import set_ecs_settings
from ecs_composex.utils.init_s3 import create_bucket


def test_ecs_settings():
    session = boto3.session.Session()
    here = path.abspath(path.dirname(__file__))
    pill = placebo.attach(session=session, data_path=f"{here}/x_ecs_settings")
    pill.playback()
    set_ecs_settings(session)
    create_bucket("ecs-composex-eu-west-1", session)
    create_bucket("ecs-composex-eu-west-2", session)
    create_bucket("cfn-templates", session)
