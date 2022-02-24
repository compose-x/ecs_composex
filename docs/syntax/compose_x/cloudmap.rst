
.. meta::
    :description: ECS Compose-X AWS CloudMap
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Route53, AWS CloudMap, dns

.. _cloudmap_reference_syntax:

=========================
x-cloudmap
=========================

This module allows you to specify one or more AWS CloudMap PrivateNamespace that you want to create / lookup and associate
services to.

At the moment, only the ECS Services are registered against CloudMap, but in a future version, you will be able to
register other services in CloudMap.

.. warning::

    This module replaces the deprecated x-dns.PrivateNamespace module & resource.

Syntax
=======

.. code-block:: yaml

    x-cloudmap:
      domain-01:
        ZoneName: example.com
        Properties: {}
        Lookup: {}


Examples
==========

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


JSON Schema
===========

Representation
----------------
.. jsonschema:: ../../../ecs_composex/specs/x-cloudmap.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/specs/x-cloudmap.spec.json
