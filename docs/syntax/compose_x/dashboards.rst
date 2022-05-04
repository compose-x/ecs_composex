
.. meta::
    :description: ECS Compose-X AWS CloudWatch dashboards
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CloudWatch dashboards

.. _dashboards_syntax_reference:

===============
x-dashboards
===============


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

Define and create CloudWatch dashboards with predefined template for your services.
Future release will allow to create custom dashboards from your own input template.

Examples
============

.. literalinclude:: ../../../use-cases/dashboards/simple.yaml
    :language: yaml
    :caption: Simple dashboard with 2 services metrics

JSON Schema
==============

Model
---------------

.. jsonschema:: ../../../ecs_composex/dashboards/x-dashboards.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/dashboards/x-dashboards.spec.json
    :language: json


Test files
==========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/dashboards>`__ to use
as reference for your use-case.
