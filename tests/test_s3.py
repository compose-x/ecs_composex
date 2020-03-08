#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ecs_composex` package."""

import json
from os import environ
from ecs_composex.common.templates import (
    check_bucket, upload_template
)

try:
    BUCKET = environ['KNOWN_BUCKET']
except KeyError:
    BUCKET = 'lambda-dev-eu-west-1'


def test_s3_bucket():
    """
    Test s3 bucket
    """
    assert check_bucket(BUCKET)


def test_s3_upload():
    """
    Tests s3 upload function
    """
    upload_template(
        json.dumps({'Test': True}),
        BUCKET,
        'test.json',
        validate=False
    )
