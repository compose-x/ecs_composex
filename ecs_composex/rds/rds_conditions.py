#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
ecs_composex.rds conditions for CFN. Allows to implement conditional logic in native CFN format.
"""

from troposphere import And, Condition, Equals, Not, Or, Ref, Select, Split

from ecs_composex.rds.rds_params import DB_ENGINE_NAME, DB_SNAPSHOT_ID, DBS_SUBNET_GROUP

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
