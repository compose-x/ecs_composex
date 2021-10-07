.. meta::
    :description: ECS Compose-X docker_opts extension
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, security, docker_opts, repositories

.. _composex_docker_opts_extension:


=======================
services.x-docker_opts
=======================

Syntax Reference
==================

.. code-block::

    services:
      serviceA:
        image: 012345678912.dkr.region.amazonaws.com/repo:tag
        x-docker_opts:
          InterpolateWithDigest: bool

.. seealso::

    For more structural details, see `JSON Schema`_



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

.. jsonschema:: ../../../../ecs_composex/specs/services.x-docker_opts.spec.json

.. literalinclude:: ../../../../ecs_composex/specs/services.x-docker_opts.spec.json
