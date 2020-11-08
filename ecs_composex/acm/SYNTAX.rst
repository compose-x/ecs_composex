.. _acm_syntax_reference:

x-acm
=====

This module is here to allow people to create ACM certificates, auto-validate these with their DNS registration,
and front their applications with HTTPS.

It recently got supported by CloudFormation to natively add the CNAME entry to your Route53 DNS record as the certificate
is created, removing the manual validation process.

.. code-block:: yaml

    x-acm:
      public-acm-01:
        Properties:
          DomainName: test.lambda-my-aws.io
          DomainValidationOptions:
            - HostedZoneId: ZABCDEFGHIS0123
              DomainName: test.lambda-my-aws.io
          SubjectAlternativeNames:
            - anothertest.lambda-my-aws.io
            - yet.another.test.lambda-my-aws.io
          ValidationMethod: DNS

.. hint::

    If you need to specify `x-dns` in the template and provide the **HostedZoneId** which will be used there.
    DNS Reference: :ref:`dns_reference_syntax`

.. warning::

    You cannot be creating your public DNS Zone and validating it at the same time, simply because the NS servers
    of you new Public Zone are not registered in your DNS registra. Therefore, DNS validation would never work.
    To that effect, you **must** (at this time) be using an existing DNS Zone in Route53.

Properties
----------

The properties will be supported exactly like in the native AWS CloudFormation definition.

.. hint::

    If you defined multiple **SubjectAlternativeNames** names, they will be auto-added to the validation list and use
    the same ZoneId

Settings
--------

No settings available at this time.

Services
--------

No need to indicate services to assign the ACM certificate to. Refer to :ref:`elbv2_syntax_reference` for mapping
to ALB/NLB.
