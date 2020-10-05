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


from troposphere import AWS_NO_VALUE
from troposphere import Ref, Tags
from troposphere import dynamodb

from ecs_composex.common import keyisset, LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.dynamodb import metadata


def define_global_sec_indexes(properties):
    """
    :param properties:
    :return:
    """
    if not keyisset("GlobalSecondaryIndexes", properties):
        return Ref(AWS_NO_VALUE)
    global_sec_index = []
    for gs in properties["GlobalSecondaryIndexes"]:
        gs_obj = dynamodb.GlobalSecondaryIndex(
            IndexName=gs["IndexName"],
            KeySchema=define_key_schema(gs["KeySchema"]),
            Projection=define_projection(gs["Projection"]),
        )
        if keyisset("ProvisionedThroughput", gs):
            gs_obj.ProvisionedThroughput = define_provisioned_throughput(gs)
        global_sec_index.append(gs_obj)
    return global_sec_index


def define_stream_spec(properties):
    """
    Function to define Table stream specs

    :param dict properties:
    :return:
    """
    if keyisset("StreamSpecification", properties) and keyisset(
        "StreamViewType", properties["StreamSpecification"]
    ):
        return dynamodb.StreamSpecification(
            StreamViewType=properties["StreamSpecification"]["StreamViewType"]
        )
    return Ref(AWS_NO_VALUE)


def define_ttl_spec(properties):
    """
    Defines TTL for Dynamodb Table

    :param dict properties:
    :return: TTL Specification
    :rtype: dynamodb.TimeToLiveSpecification
    """
    ttl_params = (
        properties["TimeToLiveSpecification"]
        if keyisset("TimeToLiveSpecification", properties)
        else {}
    )
    if ttl_params:
        required_keys = ["AttributeName", "Enabled"]
        if not all(key in required_keys for key in ttl_params.keys()):
            raise KeyError(
                "TTL Specification requires", required_keys, "Got", ttl_params.keys()
            )
        dynamodb.TimeToLiveSpecification(
            AttributeName=ttl_params["AttributeName"],
            Enabled=ttl_params["Enabled"],
        )
    return Ref(AWS_NO_VALUE)


def define_sse_spec(properties):
    return dynamodb.SSESpecification(
        SSEEnabled=True
        if keyisset("SSESpecification", properties)
        and keyisset("SSEEnabled", properties["SSESpecification"])
        else False
    )


def define_pit_spec(properties):
    pit_recover = (
        True
        if keyisset("PointInTimeRecoverySpecification", properties)
        and keyisset(
            "PointInTimeRecoveryEnabled", properties["PointInTimeRecoverySpecification"]
        )
        else False
    )
    return dynamodb.PointInTimeRecoverySpecification(
        PointInTimeRecoveryEnabled=pit_recover
    )


def define_projection(projection_def):
    projection = dynamodb.Projection()
    if keyisset("NonKeyAttributes", projection_def):
        projection.NonKeyAttributes = projection_def["NonKeyAttributes"]
    if keyisset("ProjectionType", projection_def):
        projection.ProjectionType = projection_def["ProjectionType"]
    return projection


def define_local_secondary_index(properties):
    if not keyisset("LocalSecondaryIndexes", properties):
        return Ref(AWS_NO_VALUE)
    required_keys = dynamodb.LocalSecondaryIndex.props.keys()
    local_secondary_index = properties["LocalSecondaryIndexes"]
    local_sec_index = []
    for index in local_secondary_index:
        if not all(req_keys in required_keys for req_keys in index.keys()):
            raise KeyError(
                "LocalSecondaryIndexes require parameters",
                required_keys,
                "Got",
                index.keys(),
            )
        local_sec_index.append(
            dynamodb.LocalSecondaryIndex(
                IndexName=index["IndexName"],
                KeySchema=define_key_schema(index["KeySchema"]),
                Projection=define_projection(index["Projection"]),
            )
        )
    return local_sec_index


def define_provisioned_throughput(properties):
    if keyisset("ProvisionedThroughput", properties):
        props = properties["ProvisionedThroughput"]
        return dynamodb.ProvisionedThroughput(
            ReadCapacityUnits=int(props["ReadCapacityUnits"])
            if keyisset("ReadCapacityUnits", props)
            else Ref(AWS_NO_VALUE),
            WriteCapacityUnits=int(props["WriteCapacityUnits"])
            if keyisset("WriteCapacityUnits", props)
            else Ref(AWS_NO_VALUE),
        )
    return Ref(AWS_NO_VALUE)


def define_key_schema(key_schema):
    key_schemas = []
    for schema in key_schema:
        key_schemas.append(
            dynamodb.KeySchema(
                AttributeName=schema["AttributeName"], KeyType=schema["KeyType"]
            )
        )
    return key_schemas


def define_attributes_definition(attribute_definitions):
    attributes = []
    for attribute in attribute_definitions:
        attributes.append(
            dynamodb.AttributeDefinition(
                AttributeName=attribute["AttributeName"],
                AttributeType=attribute["AttributeType"],
            )
        )
    return attributes


def define_table(table):
    """
    Function to create the DynamoDB table resource

    :param table:
    :type table: ecs_composex.common.compose_resources.Table
    """
    required_keys = ["AttributeDefinitions", "KeySchema"]
    if not all(
        required_key in table.properties.keys() for required_key in required_keys
    ):
        raise KeyError("You must at least specify table.properties", required_keys)
    table_props = {
        "AttributeDefinitions": define_attributes_definition(
            table.properties["AttributeDefinitions"]
        ),
        "KeySchema": define_key_schema(table.properties["KeySchema"]),
        "ProvisionedThroughput": define_provisioned_throughput(table.properties),
        "LocalSecondaryIndexes": define_local_secondary_index(table.properties),
        "PointInTimeRecoverySpecification": define_pit_spec(table.properties),
        "SSESpecification": define_sse_spec(table.properties),
        "TimeToLiveSpecification": define_ttl_spec(table.properties),
        "StreamSpecification": define_stream_spec(table.properties),
        "GlobalSecondaryIndexes": define_global_sec_indexes(table.properties),
        "BillingMode": table.properties["BillingMode"]
        if keyisset("BillingMode", table.properties)
        else Ref(AWS_NO_VALUE),
        "Tags": Tags(
            Name=table.name,
            ResourceName=table.logical_name,
            CreatedByComposex=True,
            RootStackName=Ref(ROOT_STACK_NAME),
        ),
        "Metadata": metadata,
    }
    cfn_table = dynamodb.Table(table.logical_name, **table_props)
    table.cfn_resource = cfn_table


def generate_table(table):
    """
    Function to add or lookup the DynamoDB table

    :param table:
    :type table: ecs_composex.common.compose_resources.Table
    :return: table
    :rtype: dynamodb.Table or None
    """
    if table.lookup:
        LOG.info("If table is found, its ARN will be added to the task")
        return
    if not table.properties:
        LOG.warning(f"Properties for table {table.name} were not defined. Skipping")
        return
    define_table(table)
    return table
