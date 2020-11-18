.. _x_configs_network_syntax:

==================
network
==================

.. code-block:: yaml

    use_cloudmap: bool
    ingress: {ingress_definition}


use_cloudmap
============


ingress definition
==================

This allows you to define specific ingress control from external sources to your environment. For example, if you have
to whitelist IP addresses that are to be allowed communication to the services, you can list these, and indicate their
name which will be shown in the EC2 security group description of the ingress rule.

.. code-block:: yaml
    :caption: Ingress Example

    x-configs:
      app01:
        network:
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

    To see details about the Ingress default syntax, refer to :ref:`ingress_syntax_ref`
