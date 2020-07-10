# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
ECS ComposeX - VPC module to simplify testing and deployment of services into AWS
"""

from ecs_composex.vpc.vpc_template import generate_vpc_template


def create_vpc_template(settings):
    """Function to create the vpc template for a combined deployment. Invoked by CLI

    :param settings: The Execution settings
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return: vpc_template Template()
    :rtype: troposphere.Template
    """
    template = generate_vpc_template(
        settings.vpc_cidr, settings.aws_azs, single_nat=settings.single_nat
    )
    return template
