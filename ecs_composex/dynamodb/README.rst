.. _dynamodb_readme:

===============
AWS DynamoDB
===============

.. hint::

    All current DynamoDB properties are supported. This feature was tested from copy-pasting the AWS examples.
    Find examples in *use-cases/dynamodb* of this repository

.. seealso::

    `AWS CFN Dynamodb Documentation`_
    :ref:`dynamodb_syntax_reference`


IAM Access types
================

Three access types have been created for the table:

* RW
* RO
* PowerUser

.. literalinclude:: ../../ecs_composex/dynamodb/dynamodb_perms.json
    :caption: DynamoDB permissions scaffold
    :language: json


.. _AWS CFN Dynamodb Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html
