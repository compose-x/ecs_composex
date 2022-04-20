
.. meta::
    :description: ECS Compose-X AWS DynamoDB syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS DynamoDB, dynamodb, serverless

.. _dynamodb_syntax_reference:

===========
x-dynamodb
===========

This module allows you to create / use existing DynamoDB tables and link them logically to the services (and other
AWS resources, where applicable).

Syntax Reference
=================

.. code-block:: yaml
    :caption: Syntax reference

    x-dynamodb:
      table-A:
        Properties: {}
        MacroParameters: {}
        Services: {}


Properties
===========

Refer to `AWS CFN Dynamodb Documentation`_. We support all of the definition and test with the documentation examples.

.. literalinclude:: ../../../use-cases/dynamodb/table_with_gsi.yml
    :language: yaml
    :caption: Tables with GSI

.. note::

    You may set the `TableName`_ property yourselves, or let AWS CloudFormation set one for you. If you set it yourselves,
    as per the documentation, that table will be replaced with a new table using the new name. Set it at your own risks.


Lookup
======

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
