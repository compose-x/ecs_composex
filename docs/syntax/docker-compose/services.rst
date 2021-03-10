.. meta::
    :description: ECS Compose-X docker-compose services syntax support
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, ecs-composex, services

.. _services_syntax_reference:

========
services
========

We try to re-use as much as possible the docker compose (v3) reference as much as possible.

For the definition of the services, you can simply use the already existing Docker compose definition for your services.
Most of the docker-compose services keys are functional, to get a full breakdown, check the :ref:`docker_compose_compat_matrix` compatibily matrix.


.. seealso::

    `Docker Compose 3 file reference <https://docs.docker.com/compose/compose-file/compose-file-v3/>`__


.. note::

    Any property in the docker-compose file you have today, for example, **build** is simply ignored.
    It will be neither removed nor modified


.. hint::

    Checkout the ECS ComposeX secrets definition syntax :ref:`secrets_syntax_reference` to import AWS Secrets Manager
    secrets to your container.
