
.. meta::
    :description: ECS Compose-X docker_opts extension
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, security, docker_opts, repositories

.. warning::

    DUE TO SECURITY DEPS not being fixed in the docker python library, this feature is for now disabled.
    Apologies for the inconvenience.

.. _composex_docker_opts_extension:

=======================
services.x-docker_opts
=======================

.. code-block::

    services:
      serviceA:
        image: nginx
        x-docker_opts:
          InterpolateWithDigest: bool


InterpolateWithDigest
=====================

.. warning::

    For this functionality to work, you must be running it on a machine with access to docker API engine.

When the image comes from docker_opts, we can very easily identify the image digest (sha256) for it and use that instead of a tag.
However not as human user friendly, this allows to always point to the same image regardless of tags change.

+----------+---------+
| Type     | Boolean |
+----------+---------+
| Default  | False   |
+----------+---------+
| Required | False   |
+----------+---------+

JSON Schema
============

Model
-------

.. jsonschema:: ../../../../ecs_composex/specs/services.x-docker_opts.spec.json

Definition
-----------

.. literalinclude:: ../../../../ecs_composex/specs/services.x-docker_opts.spec.json
