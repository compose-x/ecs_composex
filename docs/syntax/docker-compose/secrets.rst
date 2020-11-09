.. _secrets_syntax_reference:

========
secrets
========

As you might have already used these, docker-compose allows you to define secrets to use for the application.

To help continue with docker-compose syntax compatibility, you can now declare your secret in docker-compose,
and add an extension field which will be a direct mapping to the secret name you have in AWS Secrets Manager.

.. code-block:: yaml

    secrets:
      topsecret_info:
        x-secrets:
          Name: /path/to/my/secret

    services:
      serviceA:
        secrets:
          - topsecret_info

This will automatically add IAM permissions to **the execution** role of your Task definition and will export the secret
to your container, using the same name as in the compose file.

.. note::

    Only Fargate 1.4.0+ Platform Version supports secrets JSON Key

.. hint::

    If you believe that your service application should have access to the secret via **Task Role**, simply add to the
    secret definition as follows:

    .. code-block:: yaml

        secret-name:
          x-secrets:
            Name: String
            LinksTo:
              - EcsExecutionRole
              - EcsTaskRole

.. warning::

    If you do not specify **EcsExecutionRole** when specifying **LinksTo** then you will not get the secret exposed
    to your container via AWS ECS Secrets property of your Container Definition

.. hint::

    For security purposes, the containers **envoy** and **xray-daemon** are not getting assigned the secrets.


.. seealso::

    `docker-compose secrets reference`_


.. _docker-compose secrets reference: https://docs.docker.com/compose/compose-file/#secrets
