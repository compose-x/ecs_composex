.. meta::
    :description: ECS Compose-X Route53
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Route53, AWS CloudMap, dns

.. _route53_reference_syntax:

=========================
x-route53
=========================

This module allows you to create new Route53 zones and lookup existing ones.
Generally we recommend to use existing zones as other features, such as x-acm auto validation,
won't work without a working hosted zone.

This will allow you to create DNS records for supported resources.

.. attention::

    This module replaces the deprecated x-dns.PublicDomain module & resource.


Description
===============

Allows to Create or Lookup Route53 Hosted Zones in your AWS Account, to use along your services.
Once you have defined the HostedZone, compose-x will use its properties to


Syntax
=======

.. code-block:: yaml

    x-route53:
      domain-01:
        ZoneName: example.com
        Properties: {}
        Lookup: {}


.. _x_route53-x_elbv2:

Use with x-elbv2
====================

To create new Alias records pointing to your ELBv2 (NLB or ALB), simply create the x-route53 zone and set use `DnsAliases` in x-elbv2.


.. code-block:: yaml

    x-route53:
      public-domain:
        ZoneName: compose-x.io
        Lookup: true

    x-elbv2:
      public-alb:
        DnsAliases:
          - Route53Zone: x-route53::public-zone
            Names:
              - traefik.compose-x.io # Will create a new record pointing to the ALB/NLB
        Properties: {}
        ...

Use with x-acm
===================

Now that AWS ACM supports DNS validation built-into AWS CloudFormation, you can combine x-rds and x-acm to create
new ACM Certificates that will automatically set the DNS records in your DNS zone.

.. code-block::

    x-route53:
      public-domain:
        ZoneName: compose-x.io
        Lookup: true

    x-acm:
      traefik-cert:
        MacroParameters:
          DomainNames:
            - test.compose-x.io
            - someother.test.compose-x.io
          Route53Zone: x-route53::public-domain


.. warning::

    Your zone must be active and functional in order to have the certificates activated. If not, the certificates
    creation won't complete, leading CFN to rollback.

.. note::

    Compose-X will verify that the DNS names you enter in the DNS validation / ELBv2 aliases are going to match with
    the x-route53 ZoneName property defined.


JSON Schema
===========

Model
--------

.. jsonschema:: ../../../ecs_composex/specs/x-route53.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/specs/x-route53.spec.json
