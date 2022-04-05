#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere.ecs import CapacityProviderStrategyItem

RES_KEY = "x-cluster"
FARGATE_PROVIDER = "FARGATE"
FARGATE_SPOT_PROVIDER = "FARGATE_SPOT"
FARGATE_PROVIDERS = [FARGATE_PROVIDER, FARGATE_SPOT_PROVIDER]
DEFAULT_STRATEGY = [
    CapacityProviderStrategyItem(
        Weight=2, Base=1, CapacityProvider=FARGATE_SPOT_PROVIDER
    ),
    CapacityProviderStrategyItem(Weight=1, CapacityProvider=FARGATE_PROVIDER),
]
