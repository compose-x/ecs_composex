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

configs
-------

Configs is a section natively supported by docker-compose. The sections allows you to define generic settings for all
services, and apply it to services.

The way the definition of settings has been implemented is to go from the generic to the specific:

* 1. configs -> composex
* 2. configs -> service name
* 3. services -> service

.. hint::

    If a setting is set in both step 1 and step 3 for example, the value that will be kept is the value from step 3.

network
^^^^^^^

This is a top section describing the network configuration in play for the service.

Subkeys of the section:

*   `ext_sources`_

*   `is_public`_

*   `use_alb`_

*   `use_nlb`_

*   `use_cloudmap`_

*   `healthcheck`_

.. code-block:: yaml

    services:
      serviceA:
        image: image
        links: []
        ports:
        - 80:80
        configs:
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

    configs:
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

use_nlb
"""""""

Some services will need TCP or UDP based load-balancing. If that is what you need, setting to true will provide your
service with an NLB to send traffic to your containers.


use_alb
"""""""

Similarly to `use_nlb`_ this however creates an application load-balancer. It will then carry its own Security Group
and all the permissions for public ingress will be set to the load-balancer security group, where only the ports defined
on the service will allow ingress from the ALB.

.. warning::

    If you set both use_alb and use_nlb to true, then ALB takes precedence.

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
        configs:
          iam:
            boundary: containers # this will resolve into arn:${partition}:iam::${accountId}:policy/containers
      serviceB:
        image: redis
        configs:
          iam:
            boundary: arn:aws:iam::aws:policy/PowerUserAccess


xray
^^^^^
This section allows to enable X-Ray to run right next to your container.
It will use the AWS original image for X-Ray Daemon and exposes the ports to the task.

Example:

.. code-block:: yaml

    configs:
      composex:
        xray:
          enabled: true

    services:
      serviceA:
        configs:
          xray:
            enabled: True

.. seealso::

    ecs_composex.ecs.ecs_service#set_xray
