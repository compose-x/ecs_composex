#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>


from os import path

import placebo
from boto3 import session

from ecs_composex.opensearch.opensearch_aws import lookup_resource


def test_lookup_opensearch_no_vpc():
    client_session = session.Session()
    here = path.abspath(path.dirname(__file__))
    pill = placebo.attach(
        session=client_session, data_path=f"{here}/placebos/lookup_x_opensearch"
    )
    # pill.record()
    pill.playback()
    # Public endpoint domain
    config = lookup_resource(
        {"Tags": [{"CreatedByComposeX": r"true"}, {"ComposeXName": r"domain-01"}]},
        session=client_session,
    )
    print(config)

    # Private (VPC) endpoint domain
    config = lookup_resource(
        {"Tags": [{"CreatedByComposeX": "true"}, {"ComposeXName": "domain-02"}]},
        session=client_session,
    )
    print(config)
