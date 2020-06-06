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

from troposphere import Ref
from troposphere.ecs import (
    ContainerDefinition,
    PortMapping,
)
from ecs_composex.ecs.ecs_params import XRAY_IMAGE


def define_xray_container(template):
    """
    Function to define the XRay container to run with the app
    :return:
    """
    template.add_parameter(XRAY_IMAGE)
    xray_container = ContainerDefinition(
        Image=Ref(XRAY_IMAGE),
        Name="AWSXRAY",
        PortMappings=[PortMapping(ContainerPort=2000, Protocol="UDP")],
        Cpu=32,
        Memory=256,
        MemoryReservation=256,
        Essential=False,
    )
    return xray_container
