

secrets
=======

.. seealso::

    `docker-compose secrets reference`_

You might have secrets in AWS Secrets Manager that you created outside of this application stack and your services
need access to it.

By defining secrets in docker-compose, you can do all of that work rather easily.
To help make it as easy in AWS, simply set `external=True` and a few other settings to indicate how to get the secret.


.. code-block:: yaml

    version: "3.8"

    services:
      servicename:
        image: abcd
        secrets:
          - abcd

    secrets:
      mysecret:
        external: true
        x-secret:
          Name: /name/in/aws
          LinkTo:
            - EcsExecutionRole
            - EcsTaskRole

x-secret
--------

Name
^^^^

The name (also known as path) to the secret in AWS Secrets Manager.


LinksTo
^^^^^^^

List to determine whether the TaskRole or ExecutionRole (or both) should have access to the Secret.
If set as TaskRole, then the secret **value will not be exposed in env vars** and only the secret name will be set.


.. _docker-compose secrets reference: https://docs.docker.com/compose/compose-file/#secrets
