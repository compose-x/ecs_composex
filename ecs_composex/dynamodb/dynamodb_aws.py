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

from ecs_composex.common import keyisset, LOG


def define_dyn_filter_tags(tags):
    """
    Function to create the filters out of tags list

    :param list tags: list of Key/Value dict
    :return: filters
    :rtype: list
    """
    filters = []
    for tag in tags:
        key = list(tag.keys())[0]
        filter_name = key
        filter_value = tag[key]
        filters.append({"Name": filter_name, "Value": filter_value})
    return filters


def get_table_tags(session, table_arn, tags=None, next_token=None):
    """
    Function to find all tags of the table via table ARN
    :param boto3.session.Session session:
    :param str table_arn:
    :param list tags:
    :param str next_token:
    :return:
    """
    if tags is None:
        tags = []
    client = session.client("dynamodb")
    if not next_token:
        tags_r = client.list_tags_of_resource(ResourceArn=table_arn)
        for tag in tags_r["Tags"]:
            tags.append(tag)
        if keyisset("NextToken", tags_r):
            return get_table_tags(session, table_arn, tags, tags_r["NextToken"])
    elif next_token:
        tags_r = client.list_tags_of_resource(ResourceArn=table_arn)
        for tag in tags_r["Tags"]:
            tags.append(tag)
    return tags


def get_tables_tags(session, tables_list):
    """
    Function to go through all tables and retrieve their tags attributes.

    :param boto3.session.Session session:
    :param list tables_list:
    :return:
    """
    tables = []
    client = session.client("dynamodb")
    for table_name in tables_list:
        table_attributes = client.describe_table(TableName=table_name)
        table_def = {"Name": table_name, "Arn": table_attributes["Table"]["TableArn"]}
        LOG.debug(table_def)
        table_def["Tags"] = get_table_tags(session, table_def["Arn"])
        tables.append(table_def)
    return tables


def get_tables_list(session, tables=None, next_token=None):
    """
    Function to retrieve the list of all tables

    :param boto3.session.Session session:
    :param list tables: List of tables to add table names to.
    :param str next_token:
    :return:
    """
    if tables is None:
        tables = []
    client = session.client("dynamodb")
    if next_token is None:
        list_r = client.list_tables()
        for table in list_r["TableNames"]:
            tables.append(table)
        if keyisset("LastEvaluatedTableName", list_r):
            return get_tables_list(session, tables, list_r["LastEvaluatedTableName"])
    elif next_token is not None:
        list_r = client.list_tables(ExclusiveStartTableName=next_token)
        for table in list_r["Tables"]:
            tables.append(table)
    LOG.debug(tables)
    return tables


def evaluate_table_tags(table, filters):
    tags = table["Tags"]
    filters_match = 0
    for tag in tags:
        tag_key = tag["Key"]
        tag_value = tag["Value"]
        for filter_r in filters:
            if isinstance(filter_r["Value"], bool):
                filter_r["Value"] = str(filter_r["Value"])
            if filter_r["Name"] == tag_key and filter_r["Value"] == tag_value:
                filters_match += 1
    return filters_match


def lookup_dyn_table(session, tags, is_global=False):
    """
    Function to look up for table based on its tags
    :param boto3.session.Session session:
    :param list tags:
    :param bool is_global:
    :return: the matching table
    :rtype: list
    """
    matching_tables = []
    filters = define_dyn_filter_tags(tags)
    filters_count = len(filters)
    tables_names = get_tables_list(session)
    tables_defs = get_tables_tags(session, tables_names)

    for table in tables_defs:
        if not keyisset("Tags", table):
            LOG.debug(f"Table {table['Name']} has no tags. Skipping")
            continue
        filters_match = evaluate_table_tags(table, filters)
        LOG.debug(f"Filters count: {filters_count}. Match: {filters_match}")
        if filters_match == filters_count:
            matching_tables.append(table)
    return matching_tables
