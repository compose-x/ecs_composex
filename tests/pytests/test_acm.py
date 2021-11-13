#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from os import path

import boto3
import botocore
import placebo
from pytest import raises

from ecs_composex.acm.acm_aws import lookup_cert_config


def test_lookup_acm():
    """

    :return:
    """
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session(profile_name="composex")
    pill = placebo.attach(session, data_path=f"{here}/x_acm_lookup")
    # pill.record()
    pill.playback()
    lookup_cert_config(
        "cert01",
        {"Tags": [{"Name": "traefik.compose-x.io"}]},
        session,
    )
