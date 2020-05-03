#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""Tests for `ecs_composex` package."""

import json
import pytest
from os import environ
from ecs_composex.common.files import check_bucket, upload_template


@pytest.fixture
def bucket_name():
    try:
        bucket = environ["KNOWN_bucket"]
    except KeyError:
        bucket = "lambda-dev-eu-west-1"
    return bucket


def test_s3_bucket(bucket_name):
    """
    Test s3 bucket
    """
    assert check_bucket(bucket_name)


def test_s3_upload(bucket_name):
    """
    Tests s3 upload function
    """
    upload_template(
        json.dumps({"Test": True}), bucket_name, "test.json", validate=False
    )
