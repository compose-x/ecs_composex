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

import boto3
import placebo
from os import path
from pytest import raises


from ecs_composex.acm.acm_aws import lookup_cert_config


def test_lookup_acm():
    """

    :return:
    """
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_acm_lookup")
    pill.playback()
    # pill.record()
    lookup_cert_config(
        "cert01", {"Tags": [{"Name": "docs.ecs-composex.lambda-my-aws.io"}]}, session
    )
    with raises(ValueError):
        lookup_cert_config(
            "cert01",
            {"Tags": [{"Name": "docs.ecs-composex.lambda-my-aws.io"}]},
            session,
        )
