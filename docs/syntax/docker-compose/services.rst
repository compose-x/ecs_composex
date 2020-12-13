.. _services_syntax_reference:

========
services
========

We try to re-use as much as possible the docker compose (v3) reference as much as possible.

For the definition of the services, you can simply use the already existing Docker compose definition for your services.
However, there are only a limited number of settings that are today working:

* `ports <https://docs.docker.com/compose/compose-file/#ports>`__
* `environment <https://docs.docker.com/compose/compose-file/#environment>`__
* `links <https://docs.docker.com/compose/compose-file/#links>`__
* `depends_on <https://docs.docker.com/compose/compose-file/#environment>`__
* `deploy <https://docs.docker.com/compose/compose-file/#deploy>`__
* `secrets <https://docs.docker.com/compose/compose-file/#secrets>`__

.. seealso::

    `Docker Compose file reference <https://docs.docker.com/compose/compose-file>`__


.. note::

    Any property in the docker-compose file you have today, for example, **build** is simply ignored.
    It will be neither removed nor modified


.. hint::

    Checkout the ECS ComposeX secrets definition syntax :ref:`secrets_syntax_reference` to import AWS Secrets Manager
    secrets to your container.
