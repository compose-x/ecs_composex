# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from os import path
from json import loads
from ecs_composex.iam.import_sam_policies import import_and_cleanse_policies


def get_access_types():
    sam_policies = import_and_cleanse_policies()
    with open(
        f"{path.abspath(path.dirname(__file__))}/kinesis_perms.json",
        "r",
        encoding="utf-8-sig",
    ) as perms_fd:
        kinesis_policies = loads(perms_fd.read())
    sam_policies.update(kinesis_policies)
    return sam_policies


ACCESS_TYPES = get_access_types()
