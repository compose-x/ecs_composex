.. _dynamodb_syntax_reference:

===========
x-dynamodb
===========

Properties
===========

See `AWS CFN Dynamodb Documentation`_

.. hint::

    We are testing using the examples provided by AWS in the documentation of DynamoDB itself!

Services
========

List of key/pair values, as for other ECS ComposeX x-resources.

Three access types have been created for the table:

* RW
* RO
* PowerUser

.. code-block:: yaml
    :caption: Services example

    x-dynamodb:
      tableA:
        Properties: {}
        Services:
          - name: serviceA
            access: RW
          - name: serviceB
            access: RO

Settings
========

The only setting available at this time is EnvNames, as for all other x-resources. Stay tuned for updates.

Lookup
======

Lookup is currently implemented for DynamoDB tables!

Examples
========

.. code-block:: yaml
    :caption: Lookup existing table

    x-dynamodb:
      tableC:
        Lookup:
          Tags:
            - name: tableC
            - key: value


.. literalinclude:: ../../../use-cases/dynamodb/table_with_gsi.yml
    :language: yaml
    :caption: Tables with GSI


.. _AWS CFN Dynamodb Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html
