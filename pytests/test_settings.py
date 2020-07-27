﻿#  -*- coding: utf-8 -*-
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

"""
Module to test ecs_composex generic oneliner raise functions.
"""

from pytest import raises

from troposphere import ImportValue
from ecs_composex.resource_settings import generate_export_strings


def test_export_attribute():
    """
    Function to verify the raise for invalid attribute
    """
    export_string = generate_export_strings("toto", "Arn")
    assert isinstance(export_string, ImportValue)

    with raises(TypeError):
        generate_export_strings("toto", 123)
