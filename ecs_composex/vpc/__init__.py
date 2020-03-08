# -*- coding: utf-8 -*-

import boto3
from ecs_composex.common import LOG
from ecs_composex.common import KEYISSET
from ecs_composex.common.aws import get_curated_azs
from ecs_composex.vpc.vpc_template import generate_vpc_template


def create_vpc_template(session=None, **kwargs):
    """Function to create the vpc template for a combined deployment. Invoked by CLI

    :param session:
    :param kwargs:

    :return: vpc_template Template()
    :rtype: troposphere.Template
    """
    azs = []
    if not KEYISSET('AwsAzs', kwargs):
        if KEYISSET('AwsRegion', kwargs):
            azs = get_curated_azs(region=kwargs['AwsRegion'])
        elif session is None:
            session = boto3.session.Session()
            azs = get_curated_azs(session=session)
        else:
            azs = get_curated_azs()

    else:
        azs = kwargs['AwsAzs']
    LOG.debug(azs)
    cidr_block = kwargs['VpcCidr']
    single_nat = KEYISSET('SingleNat', kwargs)
    template = generate_vpc_template(
        cidr_block, azs, session, single_nat=single_nat
    )
    return template
