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
