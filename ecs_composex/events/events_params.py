# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from os import path
from ecs_composex.ecs_composex import X_KEY

MOD_KEY = path.basename(path.dirname(path.abspath(__file__)))
RES_KEY = f"{X_KEY}{MOD_KEY}"
