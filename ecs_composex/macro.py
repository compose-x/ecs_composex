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

"""
Main module. Implements all the logic of the macro event parsing and generating.
Passes all the arguments to ECS ComposeX to render the CFN templates for the docker-compose file.
"""

import re
import requests
import boto3
import tempfile
from os import path, mkdir
from copy import deepcopy
from urllib.parse import urlparse

import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from ecs_composex.common import LOG, keyisset
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import process_stacks
from ecs_composex.ecs_composex import generate_full_template


def set_settings_from_remote_files(files, settings_params, folder, session=None):
    if not keyisset(ComposeXSettings.input_file_arg, settings_params):
        local_files = []
        settings_params[ComposeXSettings.input_file_arg] = local_files
    else:
        local_files = settings_params[ComposeXSettings.input_file_arg]
    if not session:
        session = boto3.session.Session()
    client = session.client("s3")
    bucket_re = re.compile(r"(?:s3://)([a-z0-9-.]+)/([\S]+$)")
    for file in files:
        if file.startswith("s3://") and bucket_re.match(file):
            try:
                bucket_name = bucket_re.match(file).groups()[0]
                file_path = bucket_re.match(file).groups()[1]
                file_name = path.basename(file_path)
                new_file_path = path.abspath(f"{folder.name}/{file_name}")
                with open(new_file_path, "wb") as fd:
                    file_r = client.get_object(Bucket=bucket_name, Key=file_path)
                    fd.write(file_r["Body"].read())
                    local_files.append(new_file_path)
            except client.exceptions.NoSuchKey:
                LOG.error(f"Failed to download the file {file} from S3")
                raise
        elif file.startswith("https://"):
            file_name = path.basename(urlparse(file).path)
            new_file_path = path.abspath(f"{folder.name}/{file_name}")
            file_r = requests.get(file)
            if not file_r.status_code == "200":
                raise FileNotFoundError(f"Unable to retrieve {file}")
            with open(new_file_path, "w") as fd:
                fd.write(file_r.text)
            local_files.append(new_file_path)


def settings_from_raw_content(settings, content, folder):
    """
    Function to define the ComposeX Settings from RAW Content
    """
    file_path = f"{folder.name}/src.yml"
    with open(file_path, "w") as fd:
        fd.write(yaml.dump(content))
    if not keyisset(ComposeXSettings.input_file_arg, settings):
        settings.update({ComposeXSettings.input_file_arg: [file_path]})


def init_settings_params(settings_params, fragment, request_id, folder):
    """
    Function to define the parameters to send to ECS ComposeX Settings

    :param dict settings_params:
    :param fragment:
    :param str request_id:
    :param folder: Temporary folder to store all the files into.
    :return:
    """
    new_fragment = {}
    settings_params.update({"command": "create"})
    if keyisset("version", fragment) or keyisset("services", fragment):
        settings_from_raw_content(settings_params, fragment, folder)
    elif keyisset("Raw", settings_params):
        settings_from_raw_content(settings_params, settings_params["Raw"], folder)
    if keyisset("ComposeFiles", settings_params):
        set_settings_from_remote_files(
            settings_params["ComposeFiles"], settings_params, folder
        )
    if not keyisset("Name", settings_params):
        settings_params.update({"Name": request_id})
    return new_fragment


def lambda_handler(event, context):
    """
    Lambda function entrypoint.
    """
    response = {"status": "success", "requestId": event["requestId"]}
    region = event["region"]
    account_id = event["accountId"]
    transform_id = event["transformId"]
    LOG.info(
        f"Processing in {region} for transform {transform_id} in account {account_id}"
    )

    params = event["params"]
    fragment = event["fragment"]
    request_id = event["requestId"]

    folder = tempfile.TemporaryDirectory(prefix=request_id)

    settings_params = deepcopy(params)

    new_fragment = init_settings_params(settings_params, fragment, request_id, folder)
    settings = ComposeXSettings(for_macro=True, **settings_params)
    settings.set_bucket_name_from_account_id()
    settings.set_azs_from_api()
    settings.deploy = True
    settings.upload = True

    root_stack = generate_full_template(settings)
    process_stacks(root_stack, settings)
    rendered_template = root_stack.stack_template.to_dict()
    for key in [
        "Resources",
        "Outputs",
        "Mappings",
        "Conditions",
        "Metadata",
    ]:
        new_fragment[key] = (
            rendered_template[key] if keyisset(key, rendered_template) else {}
        )
    if "Parameters" in new_fragment.keys():
        del new_fragment["Parameters"]
    response["fragment"] = new_fragment
    folder.cleanup()
    return response
