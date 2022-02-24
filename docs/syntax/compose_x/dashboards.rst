
.. meta::
    :description: ECS Compose-X AWS CloudWatch dashboards
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CloudWatch dashboards

.. _dashboards_syntax_reference:

===============
x-dashboards
===============

This module allows you to define and create CloudWatch dashboards with predefined template for your services.
Later will allow to create custom dashboards from your own input template.

Syntax Reference
=================

.. code-block:: yaml

    services:
      service-01: {}
      service-02: {}

    x-dashboards:
      all-services:
        Type: cloudwatch
        Services:
          service-01:
            UsePredefinedMetrics: true
          service-02:
            UsePredefinedMetrics: true


Examples
============

.. literalinclude:: ../../../use-cases/dashboards/simple.yaml
    :language: yaml
    :caption: Simple dashboard with 2 services metrics

JSON Schema
==============

Representation
---------------

.. jsonschema:: ../../../ecs_composex/specs/x-dashboards.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/specs/x-dashboards.spec.json
    :language: json
