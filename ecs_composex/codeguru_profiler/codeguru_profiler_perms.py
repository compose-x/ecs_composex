#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

from json import loads
from os import path

from ecs_composex.iam.import_sam_policies import import_and_cleanse_policies


def get_access_types():
    sam_policies = import_and_cleanse_policies()
    with open(
        f"{path.abspath(path.dirname(__file__))}/codeguru_profiler_perms.json",
        "r",
        encoding="utf-8-sig",
    ) as perms_fd:
        codeguru_profiler_policies = loads(perms_fd.read())
    sam_policies.update(codeguru_profiler_policies)
    return sam_policies


ACCESS_TYPES = get_access_types()
