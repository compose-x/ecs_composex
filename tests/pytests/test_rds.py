#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

import pytest
from os import path
from troposphere.rds import DBCluster, DBInstance

from ecs_composex.common import load_composex_file
from ecs_composex.rds.rds_db_template import determine_resource_type


@pytest.fixture()
def here():
    return path.abspath(path.dirname(__file__))


def test_rds_resource_type(here):
    """
    Function to test resource type
    """
    cluster_file_path = f"{here}/../../use-cases/rds/resource_sorting/cluster.yml"
    instance_file_path = f"{here}/../../use-cases/rds/resource_sorting/instance.yml"

    cluster_props = load_composex_file(cluster_file_path)["Properties"]
    instance_props = load_composex_file(instance_file_path)["Properties"]

    c_type = determine_resource_type("dummy", cluster_props)
    i_type = determine_resource_type("dummy", instance_props)
    assert c_type is DBCluster
    assert i_type is DBInstance
