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

Allows to discover existing resources in your account.
Everything works the same for Settings etc, only this time, you will be expected to provide a series of **Tags**.

If tables are found in your account with the provided *Tags*, then its ARN will be used in the service policy
and exposed as the value of environment variables to the microservice task role and definition.

.. code-block:: yaml
    :caption: Tags example

    x-dynamodb:
      tableC:
        Lookup:
          Tags:
            - name: tableC
            - key: value


.. tip::

    Tags keys and values are case sensitive. At this stage, this does not support regexps.


.. _AWS CFN Dynamodb Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html
