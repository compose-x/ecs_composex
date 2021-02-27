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
        Settings: {}
        Services: []

Properties
===========

Refer to `AWS CFN Dynamodb Documentation`_. We support all of the definition and test with the documentation examples.

.. literalinclude:: ../../../use-cases/dynamodb/table_with_gsi.yml
    :language: yaml
    :caption: Tables with GSI


Settings
========

See the :ref:`settings_syntax_reference` for more details.

.. hint::

    Given DynamoDB is serverless (unless using DAX), there is no **Subnets** override.


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
          - name: serviceA
            access: DynamoDBCrudPolicy

ECS Compose-X defined access names:

* RW : Allow read/write/delete on the table items
* RO: Allow read only actions on the table items

Some of the AWS SAM access:

* `DynamoDBCrudPolicy`_
* `DynamoDBReadPolicy`_
* `DynamoDBWritePolicy`_

Services
========

.. code-block:: yaml
    :caption: Define services

    Services:
      - name: serviceA
        access: RW
      - name: serviceB
        access: RO

.. _AWS CFN Dynamodb Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html
.. _DynamoDBCrudPolicy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#dynamo-db-crud-policy
.. _DynamoDBReadPolicy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#dynamo-db-read-policy
.. _DynamoDBWritePolicy:  https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#dynamo-db-write-policy
