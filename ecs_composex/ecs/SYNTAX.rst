.. _services_syntax_reference:

Services Syntax Reference
==========================

This is where we try to re-use as much as possible the docker compose (v3) reference as much as possible.
For the definition of the services, you can simply use the already existing Docker compose definition for your services.
However, there are only a limited number of settings that are today working:

* `ports <https://docs.docker.com/compose/compose-file/#ports>`_
* `environment <https://docs.docker.com/compose/compose-file/#environment>`_
* `links <https://docs.docker.com/compose/compose-file/#links>`_
* `depends_on <https://docs.docker.com/compose/compose-file/#environment>`_
* `configs`_
* `deploy`_

.. seealso::

    `Docker Compose file reference <https://docs.docker.com/compose/compose-file>`_


Something you should know
-------------------------

With the rapid adoption of service discovery and service meshes, by default, all services will be added to an AWS
CloudMap which is associated with your VPC. If however the CloudMap ID is not provided, they won't be.

I truly believe that using Service Discovery for service to service communication is the way forward.

This really allows to have the same experience on AWS as you would locally with docker compose, only this time, everything
is further isolated and only explicitly allowed traffic will be allowed.

ECS ComposeX configurations
---------------------------

This is where developers can leverage the automation implemented in ECS ComposeX to simplify access to their services,
between services themselves and from external sources too.


To define configuration specific to the service and override ECS ComposeX default settings for network configuration,
you can use the native *configs* key of Docker compose.

.. note::

    To define configuration for your service, simply create a new element/dict in the configs element of the YAML file.

x-configs
---------

Configs is a section natively supported by docker-compose. The sections allows you to define generic settings for all
services, and apply it to services.

The way the definition of settings has been implemented is to go from the generic to the specific:

* 1. x-configs -> composex
* 2. x-configs -> service name
* 3. x-services -> service

.. hint::

    If a setting is set in both step 1 and step 3 for example, the value that will be kept is the value from step 3.

network
^^^^^^^

This is a top section describing the network configuration in play for the service.

Subkeys of the section:

*   `ext_sources`_

*   `is_public`_

*   `lb_type`_

*   `use_cloudmap`_

*   `healthcheck`_

.. code-block:: yaml

    services:
      serviceA:
        image: image
        links: []
        ports:
        - 80:80
        x-configs:
          network:
            use_alb: False
            use_nlb: False
            use_cloudmap: False
            ext_sources: []
            healthcheck: {}


ext_sources
"""""""""""

This allows you to define specific ingress control from external sources to your environment. For example, if you have
to whitelist IP addresses that are to be allowed communication to the services, you can list these, and indicate their
name which will be shown in the EC2 security group description of the ingress rule.

.. code-block:: yaml

    x-configs:
      app01:
        network:
          ext_sources:
            - ipv4: 0.0.0.0/0
              protocol: tcp
              source_name: all
            - ipv4: 1.1.1.1/32
              protocol: icmp
              source_name: CloudFlareDNS

.. note::

    Future feature is to allow to input a security group ID and the remote account ID to allow ingress traffic from
    a security group owned by another of your account (or 3rd party).


is_public
"""""""""

boolean to indicate whether or not the service should be accessible publicly. If set to true, the *load balancer* associated
to the service will be made public.

lb_type
"""""""

When using a load-balancer to reach to the service, specify the Load Balancer type.
Accepted values:

* network
* application

use_cloudmap
"""""""""""""

This indicates whether or not you want the service to be added to your VPC CloudMap instance. if set to true, it will
automatically register the service to the discovery instance.

healthcheck
"""""""""""""

At this time, this does not replace the docker compose native functionality of healthcheck. It is a simplified expression of it
which is used for cloudmap or the load-balancer to register the targets.

.. note::

    This is used for network healthchecks, not service healthcheck


iam
^^^^

This section is the entrypoint to further extension of IAM definition for the IAM roles created throughout.

boundary
""""""""

This key represents an IAM policy (name or ARN) that needs to be added to the IAM roles in order to represent the IAM
Permissions Boundary.

.. note::

    You can either provide a full policy arn, or just the name of your policy.
    The validation regexp is:

    .. code-block:: python

        r"((^([a-zA-Z0-9-_.\/]+)$)|(^(arn:aws:iam::(aws|[0-9]{12}):policy\/)[a-zA-Z0-9-_.\/]+$))"

Examples:

.. code-block:: yaml

    services:
      serviceA:
        image: nginx
        x-configs:
          iam:
            boundary: containers # this will resolve into arn:${partition}:iam::${accountId}:policy/containers
      serviceB:
        image: redis
        x-configs:
          iam:
            boundary: arn:aws:iam::aws:policy/PowerUserAccess


xray
^^^^^
This section allows to enable X-Ray to run right next to your container.
It will use the AWS original image for X-Ray Daemon and exposes the ports to the task.

Example:

.. code-block:: yaml

    x-configs:
      composex:
        xray:
          enabled: true

    services:
      serviceA:
        x-configs:
          xray:
            enabled: True

.. seealso::

    ecs_composex.ecs.ecs_service#set_xray

deploy
------

The deploy section allows to set various settings around how the container should be deployed, and what compute resources
are required to run the service.

For more details on the deploy, see `docker documentation for deploy here <https://docs.docker.com/compose/compose-file/#deploy>`_

At the moment, all keys are not supported, mostly due to the way Fargate by nature is expecting settings to be.

resources
^^^^^^^^^^

The resources is probably what interests most individuals, in setting up how much CPU and RAM should be setup for the service.
I have tried to capture for various exceptions for the RAM settings, as you can find in ecs_composex.ecs.docker_tools.set_memory_to_mb

Once the container definitions are put together, the CPU and RAM requirements are put together. From there, it will automatically
select the closest valid Fargate CPU/RAM combination and set the parameter for the Task definition.

.. important::

    CPUs should be set between 0.25 and 4 to be valid for Fargate, otherwise you will have an error.

.. warning::

    At the moment, I decided to hardcode these values in the CFN template. It is ugly, but pending bigger work to allow
    services merging, after which these will be put into a CFN parameter to allow you to change it on the fly.


replicas
^^^^^^^^

This setting allows you to define how many tasks should be running for a given service.
To make this work, I simply update the MicroserviceCount parameter default value, to keep things configurable.

.. important::::

    It is important for you to know that currently, ECS Does not support restart_policy, so there is no immediate plan
    to support that value.

.. note::

    update_config will be use very soon to support replacement of services using a LB to possibly use CodeDeploy
    Blue/Green deployment.
