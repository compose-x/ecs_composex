#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

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
    lookup_cert_config(
        "cert01", {"Tags": [{"Name": "docs.ecs-composex.lambda-my-aws.io"}]}, session
    )
    with raises(ValueError):
        lookup_cert_config(
            "cert01",
            {"Tags": [{"Name": "docs.ecs-composex.lambda-my-aws.io"}]},
            session,
        )
