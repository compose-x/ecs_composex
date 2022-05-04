
.. meta::
    :description: ECS Compose-X AWS Tagging
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, tagging

.. _tagging_syntax_reference:

=======
x-tags
=======

Mapping syntax
---------------

.. code-block:: yaml
    :caption: Key/Value structure

    x-tags:
      str: value

List syntax
-------------

Alternatively, you can use the default AWS CFN implementation

.. code-block:: yaml
    :caption: List of Key/Value tags

    x-tags:
      - Key: sts
        Value: <value>


Default tags
=============

CreatedByComposeX: true         # Allows you to identify quickly if that resource was created by Compose-X
compose-x::version: <value>     # Defines which version of compose-x was used to create this resource.

JSON Schema
============

Model
---------------

.. jsonschema:: ../../../ecs_composex/specs/x-tags.spec.json

Definition
-------------

.. literalinclude:: ../../../ecs_composex/specs/x-tags.spec.json
    :language: json

.. hint::

    It is against the ECS Compose-X philosophy to tag existing resources. If you need to tag existing resources,
    you will have to find another technique to do that. Sorry for the inconvenience.
