#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from ecs_composex.common.config import ComposeXConfig
from ecs_composex.iam import add_role_boundaries, service_role_trust_policy
from troposphere.iam import Role

import pytest


@pytest.fixture
def configs():
    return {"x-configs": {"composex": {"iam": {"boundary": "toto"}}}}


def test_service_policy():
    """
    Function to evaluate the ecs_service policy
    """
    role = Role("iamrole", AssumeRolePolicyDocument=service_role_trust_policy("ec2"))
    role.to_dict()


def test_service_role_with_boundary(configs):
    """
    :param config:
    """
    config = ComposeXConfig(configs)
    assert hasattr(config, "boundary")
    role = Role("iamrole", AssumeRolePolicyDocument=service_role_trust_policy("ec2"))
    add_role_boundaries(role, config.boundary)
    assert hasattr(role, "PermissionsBoundary")
