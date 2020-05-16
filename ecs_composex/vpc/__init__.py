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

import boto3

from ecs_composex.common import LOG, keyisset, load_composex_file
from ecs_composex.common.aws import get_curated_azs
from ecs_composex.common.ecs_composex import XFILE_DEST
from ecs_composex.common.tagging import generate_tags_parameters, add_all_tags
from ecs_composex.vpc.vpc_template import generate_vpc_template


def create_vpc_template(session=None, tags=None, **kwargs):
    """Function to create the vpc template for a combined deployment. Invoked by CLI

    :param session:
    :param kwargs:

    :return: vpc_template Template()
    :rtype: troposphere.Template
    """
    if not keyisset("AwsAzs", kwargs):
        if keyisset("AwsRegion", kwargs):
            azs = get_curated_azs(region=kwargs["AwsRegion"])
        elif session is None:
            session = boto3.session.Session()
            azs = get_curated_azs(session=session)
        else:
            azs = get_curated_azs()
    else:
        azs = kwargs["AwsAzs"]
    LOG.debug(azs)
    cidr_block = kwargs["VpcCidr"]
    single_nat = keyisset("SingleNat", kwargs)
    template = generate_vpc_template(cidr_block, azs, single_nat=single_nat)
    if tags is None and keyisset(XFILE_DEST, kwargs):
        tags = generate_tags_parameters(load_composex_file(kwargs[XFILE_DEST]))
    add_all_tags(template, tags)
    return template
