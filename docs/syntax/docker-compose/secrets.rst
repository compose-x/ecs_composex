.. _secrets_syntax_reference:

========
secrets
========

As you might have already used these, docker-compose allows you to define secrets to use for the application.

To help continue with docker-compose syntax compatibility, you can now declare your secret in docker-compose,
and add an extension field which will be a direct mapping to the secret name you have in AWS Secrets Manager.

ECS ComposeX will automatically add IAM permissions to **the execution** role of your Task definition and will export the secret
to your container, using the same name as in the compose file.

.. seealso::

    `docker-compose secrets reference`_

.. hint::

    For security purposes, the containers **envoy** and **xray-daemon** are not getting assigned the secrets.


Syntax
======

.. code-block::

    x-secrets:
      Name: str
      LinksTo: []
      JsonKeys: []
      Lookup: {}

Name
----

Type: String

The name of the secret in secrets manager to use and import.

.. hint::

    If you want to put the full ARN, you can. There will be a validation for it.

LinksTo
-------

Type: List of Strings

AllowedValues:

* EcsExecutionRole
* EcsTaskRole

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

JsonKeys
--------

Type: List of objects/dicts

.. note::

    Only Fargate 1.4.0+ Platform Version supports secrets JSON Key

.. code-block:: yaml
    :caption: JsonKeys objects structure

    Key: str
    Name: str

Key
"""

Name of the JSON Key in your secret.

Name
""""

The Name of the secret specifically for the secret JSON key


Examples
========

.. code-block:: yaml
    :caption: Short example

    secrets:
      topsecret_info:
        x-secrets:
          Name: /path/to/my/secret

    services:
      serviceA:
        secrets:
          - topsecret_info

.. code-block:: yaml
    :caption: Secret with assignment to Task and Execution Role

    secrets:
      abcd: {}
      john:
        x-secrets:
          LinksTo:
            - EcsExecutionRole
            - EcsTaskRole
          Name: SFTP/asl-cscs-files-dev


.. code-block:: yaml
    :caption: Secret Looked up from Tags and Name, also using JsonKeys

    secrets:
      zyx:
        x-secrets:
          Name: secret/with/kmskey
          Lookup:
            Tags:
              - costcentre: lambda
              - composexdev: "yes"
          JsonKeys:
            - Key: username
              Name: PSQL_USERNAME
            - Key: password
              Name: PSQL_PASSWORD


.. code-block:: yaml
    :caption: Secret with assignment to Task and Execution Role

    secrets:
      abcd: {}
      john:
        x-secrets:
          LinksTo:
            - EcsExecutionRole
            - EcsTaskRole
          Name: arn:aws:secretsmanager:eu-west-1:123456789012:secret:/secret/abcd

.. _docker-compose secrets reference: https://docs.docker.com/compose/compose-file/#secrets
