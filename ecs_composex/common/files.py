#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to manage a template and wheter it should be stored in S3
"""
import pprint
from os.path import abspath

import yaml

try:
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Dumper

import json
from os import mkdir

from botocore.exceptions import ClientError
from troposphere import Template

from ecs_composex.common import FILE_PREFIX, LOG

JSON_MIME = "application/json"
YAML_MIME = "application/x-yaml"


def upload_file(
    body,
    bucket_name,
    file_name,
    settings,
    prefix=None,
    mime=None,
):
    """Upload template_body to a file in s3 with given prefix and bucket_name

    :param body: Template body, would come from troposphere template to_json() or to_yaml()
    :type body: str
    :param bucket_name: name of the bucket to upload the file to
    :type bucket_name: str
    :param file_name: Name of the file
    :type file_name: str
    :param prefix: override default prefix for the file in S3
    :type prefix: str, optional
    :returns: url_path, the https://s3.amazonaws.com/ URL to the file
    :rtype: str
    """
    if mime is None:
        mime = JSON_MIME
    if prefix is None:
        prefix = FILE_PREFIX

    key = f"{prefix}/{file_name}"
    client = settings.session.client("s3")
    client.put_object(
        Body=body,
        Key=key,
        Bucket=bucket_name,
        ContentEncoding="utf-8",
        ContentType=mime,
        ServerSideEncryption="AES256",
    )
    return f"https://s3.amazonaws.com/{bucket_name}/{key}"


class FileArtifact(object):
    """
    Class to handle files artifacts, such as configuration files or templates.
    It will allow to upload the content to S3 or write to local filesystem.
    It also handles CloudFormation templates validation.

    :cvar str url: The URL in S3 where the file will be uploaded to or available from.
    :cvar str body: The content of the FileArtifact
    :cvar troposphere.Template template: the CFN template
    :cvar str file_name: the base name of the file
    :cvar str mime: MIME-type of the file
    :cvar boto3.session.Session session: session for clients to make API calls to AWS
    :cvar bool can_upload: Indicate whether or not config allows for upload to S3.
    :cvar bool no_upload: Turns off upload if True
    :cvar bool validate: Indicates whether the template is validated.
    :cvar str output_dir: Path to the local director to output the file to.
    :cvar str file_path: Output file path for the FileArtifact
    """

    mime = "text/plain"
    file_path = None

    def __init__(
        self, file_name, settings, file_format=None, template=None, content=None
    ):
        """
        Init method for FileArtifact

        :param file_name: Name of the file. Mandatory
        :param template: If you are providing a template to generate
        """
        self.template = None
        self.content = None
        self.file_name = file_name
        self.body = None
        self.url = None
        if file_format is None:
            file_format = settings.format
        if template is not None and not isinstance(template, Template):
            raise TypeError("template must be of type", Template, "got", type(template))
        elif (
            content is not None
            and not isinstance(content, (tuple, dict, str, list))
            and template is None
        ):
            raise TypeError(
                "content must be of type", tuple, dict, str, list, "Got", type(content)
            )
        elif (
            content is None and template is not None and isinstance(template, Template)
        ):
            self.template = template
        elif template is None and isinstance(content, (tuple, dict, str, list)):
            self.content = content
        if file_format is not None and not isinstance(file_format, str):
            raise TypeError("format is of type", type(file_format), "expected", str)
        self.define_file_specs(file_name, file_format, settings)
        self.file_path = f"{settings.output_dir}/{self.file_name}"

    def __repr__(self):
        return self.file_path

    def upload(self, settings):
        """
        Method to handle uploading the files to S3.
        """
        self.url = upload_file(
            body=self.body,
            settings=settings,
            bucket_name=settings.bucket_name,
            file_name=self.file_name,
            mime=self.mime,
        )
        LOG.info(f"{self.file_name} uploaded successfully to {self.url}")

    def write(self, settings):
        """
        Method to write the files to local filesystem based on parameters (directory name etc.)
        """
        try:
            mkdir(settings.output_dir)
            LOG.debug(f"Created directory {settings.output_dir} to store files")
        except FileExistsError:
            LOG.debug(f"Output directory {settings.output_dir} already exists")
        with open(self.file_path, "w") as template_fd:
            template_fd.write(self.body)
            if settings.no_upload:
                LOG.info(
                    f"Template {self.file_name} written successfully at {abspath(self.file_path)}"
                )

    def validate(self, settings):
        """
        Method to validate the CloudFormation template, either via URL once uploaded to S3 or via TemplateBody
        """
        try:
            if not settings.no_upload and self.url:
                settings.session.client("cloudformation").validate_template(
                    TemplateURL=self.url
                )
            elif settings.no_upload or not self.url:
                if not self.file_path:
                    self.write(settings)
                LOG.debug(f"No upload - Validating template body - {self.file_path}")
                if len(self.body) >= 51200:
                    LOG.warning(
                        f"Template body for {self.file_name} is too big for local validation."
                        " No upload is True, so skipping."
                    )
                else:
                    settings.session.client("cloudformation").validate_template(
                        TemplateBody=self.body
                    )
            LOG.debug(f"Template {self.file_name} was validated successfully by CFN")
        except ClientError as error:
            LOG.error(error)
            with open(f"/tmp/{settings.name}.{settings.format}", "w") as failed_file_fd:
                failed_file_fd.write(self.body)
                LOG.error(
                    f"Failed validation template written at /tmp/{settings.name}.{settings.format}"
                )
                raise

    def define_body(self):
        """
        Method to define the body of the file artifact. Sets the mime type that will be used for upload into S3.
        """
        if isinstance(self.template, Template):
            try:
                if self.mime == YAML_MIME:
                    self.body = self.template.to_yaml()
                else:
                    self.body = self.template.to_json()
            except Exception as error:
                pp = pprint.PrettyPrinter(indent=2)
                pp.pprint(self.template.to_dict())
                raise error
        elif isinstance(self.content, (list, dict, tuple)):
            if self.mime == YAML_MIME:
                self.body = yaml.dump(self.content, Dumper=Dumper)
            elif self.mime == JSON_MIME:
                self.body = json.dumps(self.content, indent=4)

    def define_file_specs(self, file_name, file_format, settings):
        """
        Method to set the file body from template if self.template is Template

        :param file_name: name of the file
        :param file_format: format to use for the file.
        :param settings: The settings for execution
        :return:
        """
        if file_format is not None and file_format in settings.allowed_formats:
            self.file_name = f"{file_name}.{file_format}"

        if self.file_name.endswith(".json"):
            self.mime = JSON_MIME
        elif self.file_name.endswith(".yml") or self.file_name.endswith(".yaml"):
            self.mime = YAML_MIME
        else:
            self.mime = JSON_MIME
            self.file_name = f"{self.file_name}.template"
