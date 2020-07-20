From docker-compose to AWS ECS
==============================

This module is responsible to understanding the docker compose file as a whole and then more specifically putting
together the settings of the services defined.

services
---------

The services are defined in YAML under the `services` section.
Each service then has its own set of properties that can be defined.

.. seealso::

    `Docker Compose file reference`_

.. _Docker Compose file reference: https://docs.docker.com/compose/compose-file

x-configs
---------

To enable further configuration and customization in an easy consumable format, still ignored by docker-compose natively,
you can define **x-configs** into the services definitions.

.. seealso::

    :ref:`services_syntax_reference`
