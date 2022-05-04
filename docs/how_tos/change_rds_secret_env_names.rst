
.. meta::
    :description: ECS Compose-X How To
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, rds, secrets


.. _how_to_change_aws_rds_env_vars:

============================================================
Change AWS RDS / DocumentDB secret environment variables
============================================================

The "off-the-shelves" application use-case
---------------------------------------------

Some applications out there have been written to use environment variables values for connecting to databases, and
otherwise other systems. The example list is long, but let's take an example from `awesome-compose`_ : `nexcloud-postgres`_


The docker compose file itself is pretty straightforward

.. code-block:: yaml

    services:
      nc:
        image: nextcloud:apache
        environment:
          - POSTGRES_HOST=db
          - POSTGRES_PASSWORD=nextcloud
          - POSTGRES_DB=nextcloud
          - POSTGRES_USER=nextcloud
        ports:
          - 80:80
        restart: always
        volumes:
          - nc_data:/var/www/html
      db:
        image: postgres:alpine
        environment:
          - POSTGRES_PASSWORD=nextcloud
          - POSTGRES_DB=nextcloud
          - POSTGRES_USER=nextcloud
        restart: always
        volumes:
          - db_data:/var/lib/postgresql/data
        expose:
          - 5432
    volumes:
      db_data:
      nc_data:

We can see that nexcloud uses 3 environment variables to log into our postgres DB:

.. code-block:: yaml

    environment:
      - POSTGRES_HOST=db
      - POSTGRES_PASSWORD=nextcloud
      - POSTGRES_DB=nextcloud
      - POSTGRES_USER=nextcloud

Now, of course, this application might not be the most relevant to run into AWS, but it is a relevant example as
so many other examples, such as the ones you can find in awesome-compose.

Deploying into AWS
---------------------

Deploying to AWS, one wants to use RDS. Here, let's use Aurora PostgreSQL and we will not be deploying the **db** service
defined in the docker-compose file. Instead, we use x-rds as follows:


.. code-block::
    :caption: Adding x-rds to create the NextCloud DB

    x-rds:
      nextcloud-db:
        Properties:
          DatabaseName: nextcloud
          StorageEncrypted: True
        MacroParameters:
          EngineName: "aurora-postgres"
          EngineVersion: "12.0"
        Services:
          nc:

Using x-rds, a DB Secret will be automatically created with the new RDS Cluster, using the format described in :ref:`rds_db_credentials`.
By default, compose-x would only expose the one environment variable to the service, with the secret as a string.
That obviously would require for us to change the code of nextcloud to parse that string, and use the appropriate value.
Which is not acceptable.

So, we resort to using :ref:`rds_db_secrets_mappings`. So, expanding on the example above, we have two options


.. code-block::
    :caption: Set environment variables for all services

    x-rds:
      nextcloud-db:
        Properties:
          DatabaseName: nextcloud
          StorageEncrypted: True
        MacroParameters:
          EngineName: "aurora-postgres"
          EngineVersion: "12.0"
          SecretsMappings:
            Mappings:
              - SecretName: host
                VarName: POSTGRES_HOST
              - SecretName: password
                VarName: POSTGRES_PASSWORD
              - SecretName: username
                VarName: POSTGRES_USER
              - SecretName: database
                VarName: POSTGRES_DB
        Services:
          nc:


.. code-block::
    :caption: Set environment variables specifically for one service.

    x-rds:
      nextcloud-db:
        MacroParameters:
          EngineName: "aurora-postgres"
          EngineVersion: "12.0"
        Services:
          nc:
            SecretsMappings:
              Mappings:
                host: POSTGRES_HOST
                password: POSTGRES_PASSWORD
                username: POSTGRES_USER
                database: POSTGRES_DB


In summary
--------------------

Most applications today have configuration engines that will allow for such overrides via environment variables,
which has been around for a long time, but improved even more with the adoption of Linux containers.

This demonstrates how you can easily use off-the-shelves applications and plug-and-play into AWS ecosystem and use AWS
ECS to run your containers for you, improve on security, whilst keeping simplicity.

Using the :ref:`rds_db_secrets_mappings` you can let AWS configure the secret of your application for you whilst exposing
the values to your application directly, **without additional code or logic**.

.. _awesome-compose: https://github.com/docker/awesome-compose
.. _nexcloud-postgres: https://github.com/docker/awesome-compose/tree/master/nextcloud-postgres
