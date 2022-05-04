
.. meta::
    :description: ECS Compose-X AWS CloudMap
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Route53, AWS CloudMap, dns

.. attention::

    This module replaces the deprecated x-dns.PrivateNamespace module & resource.


.. _cloudmap_reference_syntax:

=========================
x-cloudmap
=========================

.. code-block:: yaml

    x-cloudmap:
      domain-01:
        Name: example.com # You can also use ``ZoneName`` to avoid ambiguity
        Properties: {}
        Lookup: {}


Specify one or more AWS CloudMap PrivateNamespace that you want to create / lookup and associate
services to.


Use with services
===================

The below snippet illustrates how to link a namespace to services so that they get registered in service discovery.
``x-cloudmap`` can be a key/value where value is a string, simply the name of the namespace to register the service with.
It will then pick up the first port in the list of ports

When defined as a mapping (dict) you can then, at the moment, specify which port to use for the SRV record.

.. note::

    If your service does not have defined ports, it won't be registered in service discovery even if you define ``x-cloudmap`` for it.

.. code-block:: yaml

    x-cloudmap:
      private-namespace:
        ZoneName: testing.cluster

    services:
      serviceA:
        ports:
          - 8080:80
          - 8443:443
        x-network:
          x-cloudmap:
            private-namespace: # Name of the x-cloudmap namespace you want to use
              Port: 43 # Override port when there is more than one


Examples for services
-----------------------

.. code-block:: yaml

    x-cloudmap:
      private-namespace:
        ZoneName: ecs-cluster.internal
        Lookup: true

      another-private-namespace:
        ZoneName: sub.ecs-cluster.internal
        Lookup: true

    services:
      serviceA:
        ports: [80, 443]
        x-networking:
          x-cloudmap: private-namespace # This will use first port in the list, here, 80

      serviceB:
        ports: [8080, 8443]
        x-networking:
          x-cloudmap:
            private-namespace:  # Here we override the port to use and pick one from the ports list
              Port: 8443

      serviceC:
        x-networking:
          x-cloudmap: private-namespace  # Here, we did not declare a port for serviceC. It therefore will be ignored

      serviceD:
        ports: [8081:443]
        x-networking:
          x-cloudmap: another-private-namespace  # We use another x-cloudmap namespace. Target port 443 registered in awsvpc mode.


.. _resources_settings_cloudmap:

Use with x-resources
========================

You can now register your AWS Resources, such as DynamoDB tables, RDS etc. into AWS CloudMap for service discovery.
Resources such as DynamoDB tables, SQS Queues etc., which are purely API driven, will not get registered as a DNS service
into the Namespace. However, resources such as RDS, DocumentDB, and other resources that will be in the VPC and you want
to register a custom DNS name for, will get their primary endpoint registered as CNAME.

Syntax reference
------------------

.. code-block:: yaml
    :caption: DynamoDB example

    x-cloudmap:
      private-namespace:
        ZoneName: testing.cluster

    x-dynamodb:
      tableA:
        Settings:
          # ECS ompose-X will use some predefined attributes to register.
          x-cloudmap: private-namespace

      tableB:
        Settings:
          x-cloudmap:
            Namespace: private-namespace
            ReturnValues:
              TableName: Name # CFN return value will be stored as ``Name`` in the Attributes
            AdditionalAttributes:
              ArbitraryName: SomeValue

.. code-block:: yaml
    :caption: RDS example

    x-cloudmap:
      private-namespace:
        ZoneName: testing.cluster

    x-rds:
      my-database-01:
        Settings:
          x-cloudmap: private-namespace # Here, will register default attributes and mydatabase01.testing.cluster

      my-database-02:
        Settings:
          x-cloudmap:
            Namespace: private-namespace
            DnsSettings:
              Hostname: db02 # Will result into db02.testing.cluster
            AdditionalAttributes:
              MasterSecret: /rds/my-database-02/master

.. warning::

    When registering resources with DNS Settings, such as RDS, the name of the service depends on the name of the
    resource in the compose file. If you have multiple environments, we recommend to use one namespace per environment,
    as the service can only be created once.

JSON Schema
===========

Model
----------------

.. jsonschema:: ../../../ecs_composex/cloudmap/x-cloudmap.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/cloudmap/x-cloudmap.spec.json

Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases>`__ to use
as reference for your use-case.
