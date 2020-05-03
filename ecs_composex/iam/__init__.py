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

"""Entrypoint for IAM"""

from troposphere import Sub


def service_role_trust_policy(service_name):
    """
    Simple function to format the trust relationship for a Role and an AWS Service
    used from lambda-my-aws/ozone

    :param service_name: name of the service
    :type service_name: str

    :return: policy document
    :rtype: dict
    """
    statement = {
        "Effect": "Allow",
        "Principal": {"Service": [Sub(f"{service_name}.${{AWS::URLSuffix}}")]},
        "Action": ["sts:AssumeRole"],
        "Condition": {"Bool": {"aws:SecureTransport": "true"}},
    }
    policy_doc = {"Version": "2012-10-17", "Statement": [statement]}
    return policy_doc
