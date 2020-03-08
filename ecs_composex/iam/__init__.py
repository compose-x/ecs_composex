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
        "Principal": {
            "Service": [
                Sub(f'{service_name}.${{AWS::URLSuffix}}')
            ]
        },
        "Action": ["sts:AssumeRole"],
        "Condition": {
            "Bool": {
                "aws:SecureTransport": "true"
            }
        }
    }
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [
            statement
        ]
    }
    return policy_doc
