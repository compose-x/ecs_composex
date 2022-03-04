
.. meta::
    :description: ECS Compose-X AWS Tagging
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, tagging

.. _tagging_syntax_reference:

=======
x-tags
=======

This module allows you to define tags that you want to applied to all the resources that you are creating.

Syntax Reference
==================

.. code-block:: yaml
    :caption: Key/Value structure

    x-tags:
      str: value

Alternatively, you can use the default AWS CFN implementation

.. code-block:: yaml
    :caption: List of Key/Value tags

    x-tags:
      - Key: sts
        Value: <value>

Default tags
=============

CreatedByComposeX: true # Allows you to identify quickly if that resource was created by Compose-X

JSON Schema
============

Model
---------------

.. jsonschema:: ../../../ecs_composex/specs/x-tags.spec.json

Definition
-------------

.. literalinclude:: ../../../ecs_composex/specs/x-tags.spec.json
    :language: json
