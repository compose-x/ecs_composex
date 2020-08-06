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
Module to scan and find the DB and Secret for Lookup of x-rds
"""

from ecs_composex.common import keyisset, LOG
from ecs_composex.dynamodb.dynamodb_aws import (
    define_dyn_filter_tags as define_filter_tags,
    evaluate_table_tags as evaluate_tags,
)


def get_clusters_list(session, clusters=None, next_token=None):
    """
    Function to return the list of clusters in the account

    :param session:
    :return:
    """
    if clusters is None:
        clusters = []
    client = session.client("rds")
    if next_token is None:
        clusters_r = client.describe_db_clusters(IncludeShared=True)
    else:
        clusters_r = client.describe_db_clusters(IncludeShared=True, Marker=next_token)
    for cluster in clusters_r["DBClusters"]:
        clusters.append({cluster["DBClusterArn"]: cluster})
    if keyisset("Marker", clusters_r):
        return get_clusters_list(session, clusters, next_token)
    return clusters


def find_cluster_from_tags(session, tags):
    """
    Function to find the cluster from its tags
    :return:
    """
    matching_clusters = []
    filter_tags = define_filter_tags(tags)
    tags_count = len(filter_tags)
    clusters = get_clusters_list(session)



def find_cluster(session, tags=None, cluster_id=None):
    """
    Function to find the cluster based on tags or name.

    :param boto3.session.Session session:
    :param tags:
    :param cluster_id:
    :return:
    """
    client = session.client("rds")
    if cluster_id and isinstance(cluster_id, str):
        try:
            cluster_r = client.describe_clusters(DBClusterIdentifier=cluster_id)
            if cluster_r["DBClusters"] and len(cluster_r["DBClusters"]) == 1:
                return cluster_r["DBClusters"][0]
            elif cluster_r["DBClusters"] and len(cluster_r["DBClusters"]) > 1:
                raise ValueError(
                    "More than one cluster was found with given identifier"
                )
        except client.exceptions.DBClusterNotFoundFault:
            LOG.error(f"Cluster not found with identifier {cluster_id}")
    if tags:
        cluster = find_cluster_from_tags(session, tags)
