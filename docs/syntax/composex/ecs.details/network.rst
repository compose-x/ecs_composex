.. _x_configs_network_syntax:

==================
x-network
==================

.. code-block:: yaml
    :caption: Overview

    use_cloudmap: bool
    Ingress: {ingress_definition}


.. contents::

use_cloudmap
============

Boolean to turn on or off the integration to CloudMap for the services.

.. _services_ingress_syntax_reference:

Ingress definition
==================

This allows you to define specific ingress control from external sources to your environment. For example, if you have
to whitelist IP addresses that are to be allowed communication to the services, you can list these, and indicate their
name which will be shown in the EC2 security group description of the ingress rule.

Syntax reference
-----------------

.. code-block:: yaml

    Ingress:
      ExtSources: []
      AwsSources: []
      Myself: True/False

.. code-block:: yaml
    :caption: Ingress Example

    services:
      app01:
        x-network:
          Ingress:
            ExtSources:
              - Ipv4: 0.0.0.0/0
                Name: all
              - Ipv4: 1.1.1.1/32
                Source_name: CloudFlareDNS
            AwsSources:
              - Type: SecurityGroup
                Id: sg-abcd
              - Type: PrefixList
                Id: pl-abcd
            Myself: True/False

.. note::

    Future feature is to allow to input a security group ID and the remote account ID to allow ingress traffic from
    a security group owned by another of your account (or 3rd party).

.. hint::

    The protocol is automatically detected based on the port definition.
    By default, it is TCP

.. hint::

    To see details about the Ingress for Load Balancers, refer to :ref:`load_balancers_ingress_syntax_ref`


.. hint::

    When using an ALB, you do not need to define that ALB security group etc., all inbound rules will be defined automatically
    to allow the ALB to communicate with your service!
