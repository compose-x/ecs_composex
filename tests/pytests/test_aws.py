#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

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
