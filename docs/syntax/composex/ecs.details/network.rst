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

    x-configs:
      app01:
        network:
	  ingress:
	    ext_sources:
	      - ipv4: 0.0.0.0/0
		protocol: tcp
		source_name: all
	      - ipv4: 1.1.1.1/32
		protocol: icmp
                source_name: CloudFlareDNS
	    aws_sources:
	      - type: SecurityGroup
	        id: sg-abcd
	      - type: PrefixList
		id: pl-abcd
	    myself: True/False

.. note::

    Future feature is to allow to input a security group ID and the remote account ID to allow ingress traffic from
    a security group owned by another of your account (or 3rd party).
