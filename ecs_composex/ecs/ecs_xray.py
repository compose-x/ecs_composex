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

from troposphere.ecs import (
    ContainerDefinition,
    PortMapping,
)

AWS_XRAY_IMAGE = "amazon/aws-xray-daemon"


def define_xray_container():
    """
    Function to define the XRay container to run with the app
    :return:
    """
    xray_container = ContainerDefinition(
        Image=AWS_XRAY_IMAGE,
        Name="AWSXRAY",
        PortMappings=[PortMapping(ContainerPort=2000, Protocol="UDP")],
        Cpu=32,
        Memory=256,
        Essential=False,
    )
    return xray_container
