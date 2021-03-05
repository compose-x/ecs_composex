# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from json import loads
from os import path


def get_access_types():
    with open(
        f"{path.abspath(path.dirname(__file__))}/s3_perms.json",
        "r",
        encoding="utf-8-sig",
    ) as perms_fd:
        return loads(perms_fd.read())


ACCESS_TYPES = get_access_types()
