#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

import json
import os
import sys
from os import environ, path
from tempfile import TemporaryDirectory

import requests

try:
    import zipfile
except ImportError:
    print("Failed to import zipfile. Cannot retrieve latest SAM translator release")
    sys.exit(1)


def download_url(url, save_path, chunk_size=128):
    """
    Pulls RAW using requests

    :param str url:
    :param str save_path:
    :param int chunk_size:
    :return:
    """
    r = requests.get(url, stream=True)
    with open(save_path, "wb") as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)


def find_files(filename, search_path):
    """
    Find file with given name recursively from path

    :param filename:
    :param search_path:
    :return: list of found files matching names
    :rtype: list
    """
    result = []
    for root, directory, files in os.walk(search_path):
        if filename in files:
            result.append(os.path.join(root, filename))
    return result


if __name__ == "__main__":
    DIR = TemporaryDirectory()
    ZIP_DIR = TemporaryDirectory()
    RELEASE_URL = environ.get(
        "SAM_RELEASE_URL",
        "https://github.com/aws/serverless-application-model/archive/refs/tags/v1.42.0.zip",
    )
    ZIP_FILE_PATH = f"{DIR.name}/sam.zip"
    download_url(RELEASE_URL, ZIP_FILE_PATH)
    with zipfile.ZipFile(ZIP_FILE_PATH, "r") as zip_ref:
        zip_ref.extractall(ZIP_DIR.name)
    TEMPLATE_FILE = find_files("policy_templates.json", ZIP_DIR.name)[0]
    DEST_FILE_PATH = path.abspath("ecs_composex/iam/sam_policies.json")
    print("Found source", TEMPLATE_FILE)
    with open(TEMPLATE_FILE, "r") as file_fd:
        original_content = json.loads(file_fd.read())
    print("Outputting to", DEST_FILE_PATH)
    with open(DEST_FILE_PATH, "w") as file_fd:
        file_fd.write(json.dumps(original_content, indent=2))
        file_fd.write("\n")
