
.. meta::
    :description: ECS Compose-X How To
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, secrets

===================================================
Use AWS Secrets Manager for the services secrets
===================================================

Using secrets to access databases, APIs and such is common practice, and often in docker-compose, one resolves
to using environment variables whilst developing features of an application. Sometimes, one uses the
`docker-compose secrets`_ section of the compose files to re-use such secrets across multiple services.

When deploying to `AWS ECS`_, one can use `AWS Secrets Manager`_ to store and manage said secrets, and make the value
available to the services.

So let's have a look on how to declare your secrets in a compose native format, and link it to AWS Secrets manager
managed secrets when deploying to AWS.

Exposing the secret value directly to the container as an environment variable
---------------------------------------------------------------------------------

This functionality is very useful, as it allows applications that are not AWS aware (they do not use SecretsManager)
to get values from secrets without having to make any code changes.

Let's take a simple docker-compose native example

.. code-block:: yaml

    services:
      application:
        image: some-app
        secrets:
          - DB_SECRET

    secrets:
      DB_SECRET:
        file: ./my_db_secrets

Now, say that you have created a secret in AWS Secrets Manager (with or without association to RDS or other services).
If that secret in a raw text (no key/value structure), then the secret value would be "as-is", i.e. useful for SSH Keys and such.
However, you could also have a JSON document of key/value strings,
(yes, it can be more complex, but if the value is not a string, the output might not make any sense or need further parsing),
then you can further get ECS to expose the secret values one by one, each as a separate environment variable.


Exposing the raw secret content as a string
---------------------------------------------

Let's have a look, very simply how to point to AWS secret in Secrets Manager.

.. code-block:: yaml
    :caption: Expose a simple raw string value.

    services:
      application:
        image: some-app
        secrets:
          - DB_SECRET

    secrets:
      DB_SECRET:
        file: ./my_db_secrets
        x-secrets:
          Name: /path/or/name/of/secrets/in/aws


.. note::

    If your data is a JSON string, then the value is that raw string that you can parse yourself.

Exposing key/value structure into environment variables
---------------------------------------------------------

Now, let's say we have key/value structure, and we want to expose specific keys

.. code-block:: json

    {
        "hostname": "some.dns.name.tld",
        "username": "itsme",
        "password": "averysecurepassword"
    }

.. code-block:: yaml
    :caption: Expose key/value structure into separate environment variables.

    services:
      application:
        image: some-app
        secrets:
          - DB_SECRET

    secrets:
      DB_SECRET:
        file: ./my_db_secrets
        x-secrets:
          Name: /path/or/name/of/secrets/in/aws
          JsonKeys:
            - SecretKey: hostname
            - SecretKey: username
            - SecretKey: password

The  resulting environment variables would be

.. code-block:: bash

    $ echo $hostname
    some.dns.name.tld
    $ echo $username
    itsme
    $ echo $password
    averysecurepassword

Rename the keys to specific environment variables
---------------------------------------------------------

Now, let's say we have key/value structure, and we want to rename the key to a specific environment variable name


.. code-block:: yaml
    :caption: Expose key/value structure into separate environment variables.

    services:
      application:
        image: some-app
        secrets:
          - DB_SECRET

    secrets:
      DB_SECRET:
        file: ./my_db_secrets
        x-secrets:
          Name: /path/or/name/of/secrets/in/aws
          JsonKeys:
            - SecretKey: hostname
              VarName: TARGET_HOSTNAME
            - SecretKey: username
              VarName: TARGET_USERNAME
            - SecretKey: password
              VarName: TARGET_PASSWORD

The  resulting environment variables would be

.. code-block:: bash

    $ echo $TARGET_HOSTNAME
    some.dns.name.tld
    $ echo $TARGET_USERNAME
    itsme
    $ echo $TARGET_PASSWORD
    averysecurepassword



Allow the service containers to get the secret value from API call
--------------------------------------------------------------------

If you are building an application to be AWS Native, and have implemented (our your framework, library etc. did that for you)
to retrieve the secret value in-code. To allow the service to do so, simply designate that you want the ECS Task IAM Role to
be granted access to the secret, as follows:

.. code-block:: yaml
    :caption: Expose a simple raw string value.

    services:
      application:
        image: some-app
        secrets:
          - DB_SECRET

    secrets:
      DB_SECRET:
        file: ./my_db_secrets
        x-secrets:
          Name: /path/or/name/of/secrets/in/aws
          LinksTo:
            - EcsTaskRole

Doing so, the secret won't be exposed to the service via environment variable, but your application will be able to
retrieve it.

.. hint::

    If you set the **LinksTo** property to *["EcsTaskRole", "EcsExecutionRole"]*, you will be able to use either features.

Pros & Cons
--------------

The two options have each their benefits and downsides. Here is, from experience, some guidance on how to choose.

Security
^^^^^^^^^^^^^^^^

Having the application retrieve the secret itself, is secure everywhere, all the time. Therefore one might consider it
the most safe option. However, when using AWS Fargate or EC2 nodes without any access (so no access to the host is possible),
using environment variables is just as secure.

However, if you allow SSH/SSM access to the ECS Instances, or allow some
services to have elevated access to the docker API, then one could inspect the container, and see the values in clear-text.
Equally, with ECS Remote execution, one could run *printenv* or *env* and see the values.

So this is really down to your level of automation and hardening of ECS instances.

Features
^^^^^^^^^^^^^

Naturally, retrieving the secret in-code might feel like more features, and maybe you stored in the secret something that
retrieving it from environment variable would not make practical.

However, it does not prevent you from starting your services with the wrong secret in the configuration:
when using the Secrets feature, that exposes the secret value as an environment variable, ECS itself will stop the deployment
if it either does not have sufficient permissions, or, if the secret could not be found / exist (and when using a key/value structure,
if the key does not exist).

Whilst this might sound painful, it will be highly beneficial to trigger deployment failure ahead
of the services starting and potentially not behaving the way you need it to.


The secrets rotation
^^^^^^^^^^^^^^^^^^^^^^^

This might be the one thing that, if either of the previous pros/cons were an issue to you, might tip the scale.
When you retrieve the secret from in-code, you can periodically pull the secret whenever necessary and, if the secret
had a rotation mechanism in place (i.e. RDS, DocumentDB etc.), you would be able to pull the new version of the secret.

However, when using environment variables, the value that is pulled out of the secret is set at runtime, and never refreshed.
So depending on the way the rotation of the secret has been written, one could have application that all the sudden get
permissions / access issues. The only way to get the value refreshed is to terminate the task and have new ones pull the
newer version.


Integrability
^^^^^^^^^^^^^^^^^

This might be the other reason that tips the scale, if the security and features aspect did not help, and you somehow
automated recycling of ECS Service tasks on secrets rotation: integrability.

As we have seen above, or in the :ref:`change_aws_rds_env_vars` example, some applications were not written for AWS, and
environment variables are your only option.


.. _docker-compose secrets: https://docs.docker.com/compose/compose-file/compose-file-v3/#secrets
.. _AWS ECS: https://aws.amazon.com/ecs/
.. _AWS Secrets Manager: https://aws.amazon.com/secrets-manager/
