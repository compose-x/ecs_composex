#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from os import path

import boto3
import placebo
import pytest
from troposphere import Template

from ecs_composex.common import keyisset
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs.ecs_cluster import EcsCluster, add_ecs_cluster
from ecs_composex.ecs.ecs_params import CLUSTER_NAME


@pytest.fixture
def existing_cluster():
    return {"x-cluster": {"Lookup": "test"}}


@pytest.fixture
def nonexisting_cluster():
    return {"x-cluster": {"Lookup": "test2"}}


@pytest.fixture
def existing_cluster_no_fargate():
    return {
        "x-cluster": {"Lookup": "testing"},
        "services": {
            "servicea": {
                "image": "nginx/nginx",
                "deploy": {"labels": {"ecs.compute.platform": "FARGATE"}},
            }
        },
    }


def test_ecs_cluster_lookup(existing_cluster):
    """
    Function to test the ECS Cluster Lookup
    """
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_ecs/existing_cluster")
    # pill.record()
    pill.playback()
    template = Template()
    stack = ComposeXStack("test", stack_template=template)
    settings = ComposeXSettings(
        content=existing_cluster,
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    add_ecs_cluster(stack, settings)
    assert keyisset(
        CLUSTER_NAME.title, stack.stack_template.mappings[EcsCluster.mappings_key]
    )
    assert settings.ecs_cluster.platform_override is None


def test_nonexisting_cluster(nonexisting_cluster):
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_ecs/nonexisting_cluster")
    # pill.record()
    pill.playback()
    template = Template()
    stack = ComposeXStack("test", stack_template=template)
    settings = ComposeXSettings(
        content=nonexisting_cluster,
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    add_ecs_cluster(stack, settings)
    assert not keyisset(CLUSTER_NAME.title, stack.Parameters)


def test_existing_cluster_no_fargate(existing_cluster_no_fargate):
    here = path.abspath(path.dirname(__file__))
    session = boto3.session.Session()
    pill = placebo.attach(session, data_path=f"{here}/x_ecs/cluster_no_fargate")
    # pill.record()
    pill.playback()
    template = Template()
    stack = ComposeXStack("test", stack_template=template)
    settings = ComposeXSettings(
        content=existing_cluster_no_fargate,
        session=session,
        **{
            ComposeXSettings.name_arg: "test",
            ComposeXSettings.command_arg: ComposeXSettings.render_arg,
            ComposeXSettings.format_arg: "yaml",
        },
    )
    add_ecs_cluster(stack, settings)
    assert settings.ecs_cluster.platform_override == "EC2"
