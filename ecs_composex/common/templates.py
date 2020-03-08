# -*- coding: utf-8 -*-

"""
Functions to manage a template and wheter it should be stored in S3
"""

import boto3
from botocore.exceptions import ClientError

from ecs_composex.common import DATE_PREFIX
from ecs_composex.common import LOG


def check_bucket(bucket_name, session=None, client=None):
    """
    Function that checks if the S3 bucket exists and if not attempts to create it.

    :param bucket_name: name of the s3 bucket
    :type bucket_name: str
    :param session: boto3 session to use if wanted to override settings.
    :type session: boto3.session.Session
    :param client: override client
    :type client: boto3.client

    :returns: True/False, Returns whether the bucket exists or not for upload
    :rtype: bool
    """
    if session is None:
        session = boto3.session.Session()
    region = session.region_name
    location = {'LocationConstraint': region}
    if client is None:
        client = session.client('s3')
    try:
        client.head_bucket(
            Bucket=bucket_name
        )
        LOG.debug(f'Bucket {bucket_name} available')
        return True
    except ClientError as error:
        if error.response['Error']['Code'] == '404':
            try:
                LOG.info(f"Attempting to create bucket {bucket_name}")
                client.create_bucket(
                    ACL='private',
                    Bucket=bucket_name,
                    ObjectLockEnabledForBucket=True,
                    CreateBucketConfiguration=location
                )
                LOG.info(f"Bucket {bucket_name} successfully created.")
                return True
            except Exception as error:
                LOG.error(error)
                return False
    except Exception as error:
        LOG.error(error)
        LOG.error(f'Bucket name: {bucket_name}')
        LOG.error(type(bucket_name))
        return False


def validate_template(template_body, file_name, template_url=None, session=None):
    """
    Uses AWS CFN validate-template API to validate the template

    :param template_body: Template body, would come from troposphere template to_json() or to_yaml()
    :type template_body: str
    :param file_name: Name of the file
    :type file_name: str
    :param template_url: Template URL to check if template was uploaded to S3 already, optional
    :type template_url: str
    :param session: boto3 session to override and use for the client, optional
    :type session: boto3.session.Session() to override client

    :returns: True if template is validated by CFN, false if error
    :rtype: bool
    """
    if session is None:
        client = boto3.client('cloudformation')
    else:
        client = session.client('cloudformation')

    try:
        if template_url is None:
            client.validate_template(TemplateBody=template_body)
        else:
            client.validate_template(TemplateURL=template_url)
        return True
    except Exception as error:
        LOG.error(error)
        with open(f'/tmp/{file_name}', 'w') as fd:
            fd.write(template_body.strip('\n'))
        LOG.error(f'Non valid template successfully written to /tmp/{file_name}')
    return False


def upload_template(template_body, bucket_name, file_name, validate=True,
                    prefix=None, session=None, client=None, **kwargs):
    """Upload template_body to a file in s3 with given prefix and bucket_name

    :param template_body: Template body, would come from troposphere template to_json() or to_yaml()
    :type template_body: str
    :param bucket_name: name of the bucket to upload the file to
    :type bucket_name: str
    :param file_name: Name of the file
    :type file_name: str
    :param prefix: override default prefix for the file in S3
    :type prefix: str, optional
    :param validate: Whether you want to validate the uploaded template to S3. Default: True
    :type validate: bool, optional
    :param session: boto3 session to override and use for the client, optional
    :type session: boto3.session.Session() to override client
    :param client: client override for call
    :type client: boto3.client

    :returns: url_path, the https://s3.amazonaws.com/ URL to the file
    :rtype: str
    """
    if session is None:
        session = boto3.session.Session()
    assert check_bucket(bucket_name=bucket_name, session=session)

    if prefix is None:
        prefix = DATE_PREFIX

    key = f'{prefix}/{file_name}'
    if client is None:
        client = session.client('s3')
    try:
        client.put_object(
            Body=template_body,
            Key=key,
            Bucket=bucket_name,
            ContentEncoding='utf-8',
            ContentType='application/json',
            ServerSideEncryption='AES256',
            **kwargs
        )
        url_path = f'https://s3.amazonaws.com/{bucket_name}/{key}'
        if validate:
            assert validate_template(
                template_body, file_name=file_name,
                template_url=url_path, session=session
            )
        return url_path
    except Exception as error:
        LOG.debug(error)
        return None
