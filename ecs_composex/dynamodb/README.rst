DynamoDB
===============

This python subpackage is responsible for creating the DynamoDB or **finding existing tables** based on tags.

Properties
-----------

As for all resources in ECS ComposeX, this section is here to represent the AWS CloudFormation properties you would
normally use to define all the settings.

.. hint::

    All current DynamoDB properties are supported. This feature was tested from copy-pasting the AWS examples.
    Find examples in *use-cases/dynamodb* of this repository

.. seealso::

    `AWS CFN Dynamodb Documentation`_

Lookup
-------

Lookup allows you to search for existing DynamoDB tables using tags to identify your existing resources.

IAM Access types
-----------------

Three access types have been created for the table:

* RW
* RO
* PowerUser


RW - Read/Write
^^^^^^^^^^^^^^^^^^^

This allows the micro service read and write access to the table items.

.. code-block:: json
    :caption: Read/Write policy statement snippet

    {
        "Action": [
            "dynamodb:BatchGet*",
            "dynamodb:DescribeStream",
            "dynamodb:DescribeTable",
            "dynamodb:Get*",
            "dynamodb:Query",
            "dynamodb:Scan",
            "dynamodb:BatchWrite*",
            "dynamodb:DeleteItem",
            "dynamodb:UpdateItem",
            "dynamodb:PutItem",
        ],
        "Effect": "Allow",
    }

RO - Read Only
^^^^^^^^^^^^^^^^^^^

This only allows to query information out of the table items.

.. code-block:: json
    :caption: Read Only policy statement snippet

    {
        "Action": [
            "dynamodb:DescribeTable",
            "dynamodb:Query",
            "dynamodb:Scan"
        ],
        "Effect": "Allow",
    }

PowerUser
^^^^^^^^^^^

This allows all API calls apart from create and delete the table.

.. code-block:: json
    :caption: PowerUser IAM statement snippet

    {
        "NotAction": [
            "dynamodb:CreateTable",
            "dynamodb:DeleteTable",
            "dynamodb:DeleteBackup",
        ]
    },
    "Effect": "Allow"

.. _AWS CFN Dynamodb Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html
