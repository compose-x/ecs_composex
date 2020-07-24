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


from troposphere import Ref, Sub, GetAtt
from troposphere import AWS_NO_VALUE
from troposphere import dynamodb

from ecs_composex.common import keyisset, LOG, NONALPHANUM
from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.dynamodb.dynamodb_params import TABLE_NAME_T, TABLE_ARN_T


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
            AttributeName=ttl_params["AttributeName"], Enabled=ttl_params["Enabled"],
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


def add_table_to_template(template, table_name, table_definition):
    """
    Function to create the DynamoDB table resource

    :param troposphere.Template template:
    :param str table_name: Name of the table as defined in compose file
    :param dict table_definition:
    """
    required_keys = ["AttributeDefinitions", "KeySchema"]
    table_res_name = NONALPHANUM.sub("", table_name)
    if keyisset("Lookup", table_definition):
        LOG.info("Function to lookup existing table not implemented")
    properties = table_definition["Properties"]
    if not all(required_key in properties.keys() for required_key in required_keys):
        raise KeyError("You must at least specify properties", required_keys)
    table_props = {
        "AttributeDefinitions": define_attributes_definition(
            properties["AttributeDefinitions"]
        ),
        "KeySchema": define_key_schema(properties["KeySchema"]),
        "ProvisionedThroughput": define_provisioned_throughput(properties),
        "LocalSecondaryIndexes": define_local_secondary_index(properties),
        "PointInTimeRecoverySpecification": define_pit_spec(properties),
        "SSESpecification": define_sse_spec(properties),
        "TimeToLiveSpecification": define_ttl_spec(properties),
        "StreamSpecification": define_stream_spec(properties),
        "GlobalSecondaryIndexes": define_global_sec_indexes(properties),
        "BillingMode": properties["BillingMode"]
        if keyisset("BillingMode", properties)
        else Ref(AWS_NO_VALUE),
    }
    table = dynamodb.Table(table_res_name, **table_props)
    template.add_resource(table)
    template.add_output(
        formatted_outputs(
            [{f"{TABLE_NAME_T}": Ref(table)}, {f"{TABLE_ARN_T}": GetAtt(table, "Arn")}],
            export=True,
            obj_name=table_res_name,
        )
    )
