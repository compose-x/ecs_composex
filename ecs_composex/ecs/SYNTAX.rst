ecs_composex.ecs or services
============================

This is where we try to re-use as much as possible the docker compose (v3) reference as much as possible.

For the definition of the services, you can simply use the already existing Docker compose definition for your services.

However, there are only a limited number of settings that are today working:

* ports
* environment
* links
* depends_on


Something you should know
-------------------------

With the rapid adoption of service discovery and service meshes, by default, all services will be added to an AWS
CloudMap which is associated with your VPC. If however the CloudMap ID is not provided, they won't be.

I truly believe that using Service Discovery for service to service communication is the way forward.

This really allows to have the same experience on AWS as you would locally in docker compose, only this time, everything
is further isolated and only explicitly allowed traffic will be allowed.

ECS ComposeX configurations
---------------------------

This is where developers can leverage the automation implemented in ECS ComposeX to simplify access to their services,
between services themselves and from external sources too.


To define configuration specific to the service and override ECS ComposeX default settings for network configuration,
you can use the native *configs* key of Docker compose.

.. note::

    To define configuration for your service, simply create a new element/dict in the configs element of the YAML file.


ext_sources
^^^^^^^^^^^

This allows you to define specific ingress control from external sources to your environment. For example, if you have
to whitelist IP addresses that are to be allowed communication to the services, you can list these, and indicate their
name which will be shown in the EC2 security group description of the ingress rule.

.. code-block:: yaml
    configs:
      app01:
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
^^^^^^^^^

boolean to indicate whether or not the service should be accessible publicly. If set to true, the *load balancer* associated
to the service will be made public.

use_nlb
^^^^^^^

Some services will need TCP or UDP based load-balancing. If that is what you need, setting to true will provide your
service with an NLB to send traffic to your containers.


use_alb
^^^^^^^

Similarly to `use_nlb`_ this however creates an application load-balancer. It will then carry its own Security Group
and all the permissions for public ingress will be set to the load-balancer security group, where only the ports defined
on the service will allow ingress from the ALB.

.. warning::

    If you set both use_alb and use_nlb to true, then ALB takes precedence.

use_cloudmap
^^^^^^^^^^^^

This indicates whether or not you want the service to be added to your VPC CloudMap instance. if set to true, it will
automatically register the service to the discovery instance.

healthcheck
^^^^^^^^^^^

At this time, this does not replace the docker compose native functionality of healthcheck. It is a simplified expression of it
which is used for cloudmap or the load-balancer to register the targets.

.. note::

    This is used for network healthchecks, not service healthcheck


