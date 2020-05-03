# -*- coding: utf-8 -*-

"""
Functions to manage a template and wheter it should be stored in S3
"""
import yaml

try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper
from os import path, mkdir

import boto3
import json
from botocore.exceptions import ClientError
from datetime import datetime as dt
from troposphere import Template
from ecs_composex.common.ecs_composex import DIR_DEST
from ecs_composex.common import DATE_PREFIX, KEYISSET
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
    if client is None:
        if session is None:
            session = boto3.session.Session()
        client = session.client("s3")
    region = session.region_name
    location = {"LocationConstraint": region}
    try:
        client.head_bucket(Bucket=bucket_name)
        LOG.debug(f"Bucket {bucket_name} available")
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] == "404":
            try:
                LOG.info(f"Attempting to create bucket {bucket_name}")
                client.create_bucket(
                    ACL="private",
                    Bucket=bucket_name,
                    ObjectLockEnabledForBucket=True,
                    CreateBucketConfiguration=location,
                )
                LOG.info(f"Bucket {bucket_name} successfully created.")
                return True
            except Exception as error:
                LOG.error(error)
                return False
    except Exception as error:
        LOG.error(error)
        LOG.error(f"Bucket name: {bucket_name}")
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
        client = boto3.client("cloudformation")
    else:
        client = session.client("cloudformation")

    try:
        if template_url is None:
            client.validate_template(TemplateBody=template_body)
        else:
            client.validate_template(TemplateURL=template_url)
        return True
    except Exception as error:
        LOG.error(error)
        with open(f"/tmp/{file_name}", "w") as fd:
            fd.write(template_body.strip("\n"))
        LOG.error(f"Non valid template successfully written to /tmp/{file_name}")
    return False


def upload_template(
    template_body,
    bucket_name,
    file_name,
    validate=True,
    prefix=None,
    session=None,
    client=None,
    mime=None,
    **kwargs,
):
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
    if mime is None:
        mime = "application/json"
    if prefix is None:
        prefix = DATE_PREFIX

    key = f"{prefix}/{file_name}"
    if client is None:
        client = session.client("s3")
    try:
        client.put_object(
            Body=template_body,
            Key=key,
            Bucket=bucket_name,
            ContentEncoding="utf-8",
            ContentType=mime,
            ServerSideEncryption="AES256",
            **kwargs,
        )
        url_path = f"https://s3.amazonaws.com/{bucket_name}/{key}"
        if validate:
            assert validate_template(
                template_body,
                file_name=file_name,
                template_url=url_path,
                session=session,
            )
        return url_path
    except Exception as error:
        LOG.debug(error)
        return None


class FileArtifact(object):
    """
    Class for a template file built.
    """

    url = None
    body = None
    template = None
    file_name = None
    mime = "text/plain"
    session = boto3.session.Session()
    bucket = None
    can_upload = False
    validated = False
    output_dir = f"/tmp/{dt.utcnow().strftime('%s')}"
    file_path = None

    def upload(self):
        if not self.can_upload:
            LOG.error("BucketName was not specified, not attempting upload")
        else:
            self.url = upload_template(
                self.body, self.bucket, self.file_name, mime=self.mime, validate=False
            )
            LOG.info(f"{self.file_name} uploaded successfully to {self.url}")

    def write(self):
        try:
            mkdir(self.output_dir)
            LOG.debug(f"Created directory {self.output_dir} to store files")
        except FileExistsError:
            LOG.debug(f"Output directory {self.output_dir} already exists")
        with open(self.file_path, "w") as template_fd:
            if self.body is None:
                self.define_body()
            template_fd.write(self.body)
            LOG.debug(
                f"Template {self.file_name} written successfully at {self.output_dir}/{self.file_name}"
            )

    def validate(self):
        try:
            if self.url is None:
                self.upload()
            self.session.client("cloudformation").validate_template(
                TemplateURL=self.url
            )
            LOG.debug(f"Template {self.file_name} was validated successfully by CFN")
            self.validated = True
        except ClientError as error:
            LOG.error(error)

    def define_body(self):
        if isinstance(self.template, Template):
            if self.mime == "application/x-yaml":
                self.body = self.template.to_yaml()
            else:
                self.body = self.template.to_json()
        elif isinstance(self.content, (list, dict, tuple)):
            self.can_upload = True
            if self.mime == "application/x-yaml":
                self.body = yaml.dump(self.content, Dumper=Dumper)
            elif self.mime == "application/json":
                self.body = json.dumps(self.content, indent=4)

    def define_file_specs(self):
        """
        Function to set the file body from template if self.template is Template
        """
        if self.file_name.endswith(".json"):
            self.mime = "application/json"
        elif self.file_name.endswith(".yml") or self.file_name.endswith(".yaml"):
            self.mime = "application/x-yaml"

    def set_from_kwargs(self, **kwargs):
        """
        Function to set internal settings based on kwargs keys
        :param kwargs:
        """
        if KEYISSET(DIR_DEST, kwargs):
            self.output_dir = path.abspath(kwargs[DIR_DEST])
        if KEYISSET("BucketName", kwargs):
            self.bucket = kwargs["BucketName"]
            self.can_upload = True

    def create(self):
        """
        Function to write to file and upload in a single function
        """
        self.define_body()
        self.write()
        self.upload()

    def __init__(self, file_name, template=None, content=None, session=None, **kwargs):
        """
        Init function for our template file object
        :param file_name: Name of the file. Mandatory
        :param template: If you are providing a template to generate
        :param body: raw content to write
        :param session:
        :param kwargs:
        """
        self.file_name = file_name
        if template is not None and not isinstance(template, Template):
            raise TypeError("template must be of type", Template, "got", type(template))
        elif isinstance(template, Template):
            self.template = template
        if session is not None:
            self.session = session
        self.set_from_kwargs(**kwargs)
        if content is not None and isinstance(content, (tuple, dict, str, list)):
            self.content = content
        self.define_file_specs()
        self.file_path = f"{self.output_dir}/{self.file_name}"

    def __repr__(self):
        return self.file_path
