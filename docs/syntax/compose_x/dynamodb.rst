
.. meta::
    :description: ECS Compose-X AWS DynamoDB syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS DynamoDB, dynamodb, serverless

.. _dynamodb_syntax_reference:

===========
x-dynamodb
===========

.. code-block:: yaml
    :caption: Syntax reference

    x-dynamodb:
      table-A:
        Properties: {}
        MacroParameters: {}
        Services: {}
        Scaling: {}

Create / use existing DynamoDB tables and link them logically to the services (and other AWS resources, where applicable).

Services
========

.. code-block:: yaml
    :caption: Example with 2 services

    x-dynamodb:
      table01:
        Properties: {}
        Services:
          app01:
            Access: RW
          app02:
            Access: RO
            ReturnValues: {}

ReturnValues
-------------

Refer to `AWS CFN DynamoDB Return Values`_ for these settings.

.. warning::

    If you try to retrieve ``StreamArn`` but did not set the properties for it, it will fail.

To get the table name, use ``TableName`` to get the value returned by ``Ref`` function.

Access
--------

ECS Compose-X defined access names:

* RW : Allow read/write/delete on the table items
* RO: Allow read only actions on the table items

Properties
===========

Refer to `AWS CFN Dynamodb Documentation`_. We support all of the definition and test with the documentation examples.

.. literalinclude:: ../../../use-cases/dynamodb/table_with_gsi_autoscaling.yml
    :language: yaml
    :caption: Tables with GSI and autoscaling

.. attention::

    You may set the `TableName`_ property yourselves, or let AWS CloudFormation set one for you. If you set it yourselves,
    as per the documentation, that table will be replaced with a new table using the new name. Set it at your own risks

Lookup
=======

For more details, see the :ref:`lookup_syntax_reference`.

.. code-block:: yaml
    :caption: Lookup DynamoDB Table example

    x-dynamodb:
      table-A:
        Lookup:
          Tags:
            - table-name: table123
            - owner: myself
            - costallocation: 123
        Services:
          serviceA:
            Access: DynamoDBCrudPolicy

Scaling
=========

.. note::

    This is only available to new DynamoDB tables.

.. code-block:: yaml

x-dynamodb:
  TableA:
    Properties: {}
    Scaling:
      Table: AutoscalingUnit
      Indexes:
        <index_name>: AutoscalingUnit
      CopyToIndexes: bool

AutoscalingUnit
-----------------

Allows to define the scaling properties for either ``ReadCapacityUnits`` or ``WriteCapacityUnits``

.. code-block:: yaml
    :caption: AutoscalingUnit

    ReadCapacityUnits: ScalingDefinition
    WriteCapacityUnits: ScalingDefinition

ScalingDefinition
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml
    :caption: ScalingDefinition

    MaxCapacity: number
    MinCapacity: numer
    TargetValue: number
    ScaleInCooldown: number
    ScaleOutCooldown: number

CopyToIndexes
----------------

If you want to define autoscaling on the indexes with the same properties as for the Table, setting ``CopyToIndexes`` to
true will automatically go through the GSIs of the table and set the same scaling policy as the one defined for the table.

Indexes
----------

.. code-block:: yaml

x-dynamodb:
  TableA:
    Properties: {}
    Scaling:
      Table: AutoscalingUnit
      Indexes:
        myGSI: AutoscalingUnit

Allows you define the same parameters as for the table, but on the indexes. If you set both ``CopyToIndexes`` and an
index in this section, the Index level settings take precedence.

.. tip::

    If you define scaling on an index that is not in the Properties, it will automatically flag it and fail.


JSON Schema
============

Model
----------------

.. jsonschema:: ../../../ecs_composex/dynamodb/x-dynamodb.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/dynamodb/x-dynamodb.spec.json
    :language: json

Test files
==========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/dynamodb>`__ to use
as reference for your use-case.


.. _AWS CFN Dynamodb Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html
.. _DynamoDBCrudPolicy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#dynamo-db-crud-policy
.. _DynamoDBReadPolicy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#dynamo-db-read-policy
.. _DynamoDBWritePolicy:  https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#dynamo-db-write-policy
.. _AWS CFN DynamoDB Return Values: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html#aws-resource-dynamodb-table-return-values
.. _TableName: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html#cfn-dynamodb-table-tablename
