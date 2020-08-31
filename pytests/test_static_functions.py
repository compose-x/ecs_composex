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

from pytest import raises

from ecs_composex.ecs.ecs_service import generate_security_group_props


def test_cidr_validation():
    a = generate_security_group_props({"ipv4": "1.1.1.1/32"}, "abcd")
    with raises(ValueError):
        a = generate_security_group_props({"ipv4": "1.1.1.256/32"}, "abcd")
        a = generate_security_group_props({"ipv4": "1.1.1.1/33"}, "abcd")
