x-tags
=======

This module allows you to define tags that you want to applied to all the resources that you are creating.

Syntax Reference
==================

.. code-block:: yaml

x-tags:
  str: value

Alternatively

.. code-block:: yaml

x-tags:
  - Key: sts
    Value: <value>

Default tags
=============

CreatedByComposeX: true # Allows you to identify quickly if that resource was created by Compose-X

JSON Schema
============

.. jsonschema:: ../../../ecs_composex/specs/x-tags.spec.json

.. literalinclude:: ../../../ecs_composex/specs/x-tags.spec.json
    :language: json
