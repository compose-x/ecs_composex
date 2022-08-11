# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from os import path

import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader
import pytest
from troposphere.rds import DBCluster, DBInstance

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

    with open(cluster_file_path) as composex_fd:
        cluster_props = yaml.load(composex_fd.read(), Loader=Loader)["Properties"]
    with open(instance_file_path) as composex_fd:
        instance_props = yaml.load(composex_fd.read(), Loader=Loader)["Properties"]

    c_type = determine_resource_type("dummy", cluster_props)
    i_type = determine_resource_type("dummy", instance_props)
    assert c_type is DBCluster
    assert i_type is DBInstance
