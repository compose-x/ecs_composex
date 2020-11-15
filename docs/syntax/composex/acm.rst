.. _acm_syntax_reference:

=====
x-acm
=====

This module to allow people to create ACM certificates, auto-validate these with their DNS registration, and front their applications with HTTPS.

.. hint::

    Recently got supported by CloudFormation to natively add the CNAME entry to your Route53 DNS record as the certificate
    is created, removing the manual validation process.


Syntax
======

.. code-block:: yaml

    x-acm:
      certificate-01:
        Properties: {} # AWS CFN Properties
        MacroParameters: {} # ComposeX Macro parameters for ACM


.. warning::

    You cannot be creating your public DNS Zone and validating it at the same time, simply because the NS servers
    of you new Public Zone are not registered in your DNS registra. Therefore, DNS validation would never work.
    Make sure that if you are creating a new DNS PublicZone, you will be able to use it!


Properties
==========

The properties will be supported exactly like in the native `AWS ACM Properties`_

.. hint::

    If you defined multiple **SubjectAlternativeNames** names, they will be auto-added to the validation list and use
    the same ZoneId, so you do not need to list them all in `DomainValidationOptions`_

Services
========

No need to indicate services to assign the ACM certificate to. Refer to :ref:`elbv2_syntax_reference` for mapping
to ALB/NLB.


MacroParameters
================

In the aspiration of making things easy, you can now simply define very straight forward settings to define your certificate.
This automatically creates the full ACM Certificate definition, and uses DNS validation.

.. code-block:: yaml

    DomainNames:
      - domain.tld
      - sub.domain.tld
    HostedZoneId: ZoneID


DomainNames
-----------

List of the domain names you want to create the ACM Certificate for.

.. hint::

    The first domain name will be used for the CN, and the following ones will be used for SubjectAlternative names

HostedZoneId
------------

If you wish to override the x-dns/PublicZone settings you can set that here.

.. note::

    That HostedZone ID will be used for *all* of the Domain Validation.

Example
=======

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

.. _AWS ACM Properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-certificatemanager-certificate.html
.. _DomainValidationOptions: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-certificatemanager-certificate.html#cfn-certificatemanager-certificate-domainvalidationoptions
