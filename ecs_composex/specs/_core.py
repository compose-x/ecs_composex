#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Load all the JSON Schema specification's
"""

import json
from os import listdir, path

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import (  # type: ignore[import-not-found, no-redef]
        files,
    )

from referencing import Resource


def _schemas():
    specs_folder = files("ecs_composex").joinpath("specs")
    for spec_file in listdir(specs_folder):
        if not spec_file.endswith(".spec.json"):
            continue
        with open(f"{specs_folder}/{spec_file}") as version_fd:
            contents = json.loads(version_fd.read())
        yield Resource.from_contents(contents)
