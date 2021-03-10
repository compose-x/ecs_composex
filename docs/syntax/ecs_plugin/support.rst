.. meta::
    :description: ECS Compose-X Docker ecs-plugin support syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, ecs-plugin, x-aws

.. _docker_ecs_plugin_support_reference:


===========================
Docker ECS Plugin support
===========================

Soon after the Open source release of the Compose definition, AWS and Docker worked on a new
docker plugin, the *ecs-plugin* which allows to perform some similar tasks as with ECS ComposeX.

However, these fields usually will require full ARN of your resources, whereas ECS ComposeX will
allow you to do discovery of your resources and I hope give you a lot more flexibility.

With that said, the objective of ECS ComposeX is to help developers and so I added the support for
the ECS Plugin extensions fields.

.. seealso::

    `Docker and ECS official documentation`_

.. _x-aws-cluster:

x-aws-cluster
--------------

As per the official documentation, this allows you to define the ARN of an ECS Cluster you have
that you want to use to deploy the services into.

If left empty, a new cluster gets created.

With ComposeX you can use the expected ARN to indicate which cluster to deploy to. Equally, you can
provide just the name of the Cluster, ComposeX will filter it out of the ARN and behave in a similar fashion
as **x-cluster/Use**

.. seealso::

    :ref:`ecs_cluster_syntax_reference`

.. _x-aws-pull_credentials:

x-aws-pull_credentials
-----------------------

This allows you to define the secret in secrets manager that contains the username/password for
authentication with a private docker image registry.

With ComposeX you can either use it as is defined in the official documentation or combine it with
the docker-compose secrets.

.. code-block:: yaml
    :caption: Example of ARN use

    services:
      app01:
        image: private.registry.mydomain.net/repository-app01
        x-aws-pull_credentials: "arn:aws:secretsmanager:eu-west-1:012345678912:secret:/path/to-creds"

.. code-block:: yaml
    :caption: Example with docker-compose secret definition

    secrets:
      private_repository:
        x-secrets:
          Name: /path/to/creds

    services:
      app02:
        image: private.registry.mydomain.net/repository-app02
        x-aws-pull_credentials: secrets::private_repository


.. hint::

    For either methods, this will add the RepositoryCredentials property to the Task definition
    and add an IAM policy to the Execution Role to *secretsmanager:GetSecretValue*

.. hint::

    When using the ECS ComposeX way, you can use all the existing features of secrets (Lookup etc).

.. warning::

    You cannot use JsonKeys for this secret.

.. _x-aws-autoscaling:

x-aws-autoscaling
-----------------

This setting allows you to define autoscaling configuration for your service. With the ECS Plugin
you can define CPU and RAM autoscaling which are assigned to the ECS Service.

If in your docker-compose files you have not defined **x-scaling** this will be used to define the
scaling policies.

However, in case you set both **x-aws-autoscaling** and **x-scaling**, the latter will be used and the
x-aws-autoscaling settings are ignored.

This is by design as **x-scaling** allows for a lot more settings to be defined than **x-aws-autoscaling**

.. _x-aws-policies:

x-aws-policies
---------------

This allows to define additional IAM policies that are assigned to the ECS Task Role.
It behaves exactly in the same way as **x-iam/ManagedPolicies** does.

.. code-block:: yaml
    :caption: ECS Plugin syntax

    services:
      foo:
        x-aws-policies:
          - "arn:aws:iam::aws:policy/AmazonS3FullAccess"


.. code-block:: yaml
    :caption: ECS Compose-X syntax

    services:
      foo:
        x-iam:
          ManagedPolicies:
            - "arn:aws:iam::aws:policy/AmazonS3FullAccess"

.. _x-aws-role:

x-aws-role
-----------

Allows to defined extra IAM policies. However, not that the ECS Plugin is going to automatically
generate the name of the policy assigned to the ECS Task Role.

ECS ComposeX syntax is a little lengthier to get to the IAM policies. However, allows you to define
your own policy and you can have multiple ones.

.. code-block:: yaml
    :caption: ECS Plugin syntax

    services:
      foo:
        x-aws-role:
          Version: "2012-10-17"
          Statement:
            - Effect: "Allow"
              Action:
                - "some_aws_service"
              Resource:
                - "*"

.. code-block:: yaml
    :caption: ECS ComposeX Syntax

    services:
      foo:
        x-iam:
          Policies:
            - PolicyName: SomeName
              PolicyDocument:
                Version: "2012-10-17"
                Statement:
                  - Effect: "Allow"
                    Action:
                      - "some_aws_service"
                    Resource:
                      - "*"

.. hint::

    For x-aws-role and x-aws-policies, ECS ComposeX will not override what you had defined and instead
    simply merge the two definitions.

.. hint::

    If you need to defined IAM permissions boundary, you can with ECS Compose-X.
    :ref:`x_iam_syntax_reference`

.. _x-aws-logs_retention:

x-aws-logs_retention
---------------------

Allows you to define the CloudWatch Log Group RetentionInDays period.
When used in combination with ComposeX **x-logging**, the highest(max) value will be used as we consider you might want
the longest period for tracking purposes.

If either is set and the other is not, the value is set accordingly.

.. code-block:: yaml
    :caption: Example with just x-aws-logs_retention

    services:
      serviceA:
        x-aws-logs_retention: 42

.. code-block:: yaml
    :caption: Both x-logging and x-aws-logs_retentions defined. Here, 64 will be set.

    services:
      serviceA:
        x-logging:
          RetentionInDays: 42
        x-aws-logs_retention: 64


.. seealso::

    :ref:`x_configs_logging_syntax_reference`

.. hint::

    If you set an arbitrary value that would not be a valid value for AWS logs retention, ComposeX will automatically
    match to the closest valid value. For example, for 42, this will be 30. For 64, it will be 60.

.. _x_aws_update_config:

x-aws-min_percent & x-aws-max_percent
======================================

This allows to define the percentages for ECS Deployment Configuration.

.. code-block:: yaml

    services:
      serviceA:
        x-aws-min_percent: 50
        x-aws-max_percent: 150
        deploy:
          replicas: 4
          update_config:
            failure_action: rollback


.. _Docker and ECS official documentation: https://docs.docker.com/engine/context/ecs-integration/
