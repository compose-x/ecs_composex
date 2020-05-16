# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
ecs_composex.rds conditions for CFN. Allows to implement conditional logic in native CFN format.
"""

from troposphere import Ref, Equals, Split, Select, Not, Condition, And, Or
from ecs_composex.rds.rds_params import DBS_SUBNET_GROUP, DB_ENGINE_NAME, DB_SNAPSHOT_ID

DBS_SUBNET_GROUP_CON_T = "CreateSubnetGroupCondition"
DBS_SUBNET_GROUP_CON = Equals(Ref(DBS_SUBNET_GROUP), DBS_SUBNET_GROUP.Default)

NOT_USE_DB_SNAPSHOT_CON_T = "NotUseSnapshotToCreateDbCondition"
NOT_USE_DB_SNAPSHOT_CON = Equals(Ref(DB_SNAPSHOT_ID), DB_SNAPSHOT_ID.Default)

USE_DB_SNAPSHOT_CON_T = "UseSnapshotToCreateDbCondition"
USE_DB_SNAPSHOT_CON = Not(Condition(NOT_USE_DB_SNAPSHOT_CON_T))

USE_CLUSTER_CON_T = "UseAuroraClusterCondition"
USE_CLUSTER_CON = Equals("aurora", Select(0, Split("-", Ref(DB_ENGINE_NAME))))

NOT_USE_CLUSTER_CON_T = "NotUseClusterCondition"
NOT_USE_CLUSTER_CON = Not(Condition(USE_CLUSTER_CON_T))

USE_CLUSTER_AND_SNAPSHOT_CON_T = "UseClusterAndSnapshotCondition"
USE_CLUSTER_AND_SNAPSHOT_CON = And(
    Condition(USE_CLUSTER_CON_T), Condition(USE_DB_SNAPSHOT_CON_T)
)

USE_CLUSTER_NOT_SNAPSHOT_CON_T = "UseClusterAndNotSnapshotCondition"
USE_CLUSTER_NOT_SNAPSHOT_CON = And(
    Condition(USE_CLUSTER_CON_T), Condition(NOT_USE_DB_SNAPSHOT_CON_T)
)

NOT_USE_CLUSTER_USE_SNAPSHOT_CON_T = "NotUseClusterButUseSnapshotCondition"
NOT_USE_CLUSTER_USE_SNAPSHOT_CON = And(
    Condition(NOT_USE_CLUSTER_CON_T), Condition(USE_DB_SNAPSHOT_CON_T)
)

USE_CLUSTER_OR_SNAPSHOT_CON_T = "UseSnapshotOrClusterCondition"
USE_CLUSTER_OR_SNAPSHOT_CON = Or(
    Condition(USE_CLUSTER_CON_T), Condition(USE_DB_SNAPSHOT_CON_T)
)
