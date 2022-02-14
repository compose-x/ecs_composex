.. meta::
    :description: ECS Compose-X AWS CloudMap
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Route53, AWS CloudMap, dns

.. _cloudmap_reference_syntax:

=========================
x-cloudmap - AWS CloudMap
=========================

.. note::

    This module replaces the deprecated x-dns.PrivateNamespace module & resource.

Syntax
=======

.. code-block:: yaml

    x-cloudmap:
      domain-01:
        ZoneName: example.com
        Properties: {}
        Lookup: {}


JSON Schema
===========

.. jsonschema:: ../../../ecs_composex/specs/x-cloudmap.spec.json

.. literalinclude:: ../../../ecs_composex/specs/x-cloudmap.spec.json
