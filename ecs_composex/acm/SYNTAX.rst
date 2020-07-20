.. _acm_syntax_reference:

x-acm
=====

This module is here to allow people to create ACM certificates, auto-validate these with their DNS registration,
and front their applications with HTTPS.

It recently got supported by CloudFormation to natively add the CNAME entry to your Route53 DNS record as the certificate
is created, removing the manual validation process.

.. warning::

    At the time of working on that feature, Troposphere has not released the feature for it, but is available in
    their master branch.

.. code-block::

    x-acm:
      blogdemo:
        Properties:
          DomainName: blog-demo.lambda-my-aws.io
          DomainValidationOptions:
            - DomainName: lambda-my-aws.io
              HostedZoneId: Zredacted
        Settings: {}
        Services:
          - name: app01
            ports: [443]

Properties
----------

The properties will be supported exactly like in the native AWS CloudFormation definition.
At the time of writing the module though, only 1 DomainValidation option is supported.

.. hint::

    Remember as well, you can only auto-validate with providing the HostedZoneId, and you probably only would do that
    once.

Settings
--------

No settings yet implemented. By default, the `Name` tag key will use the same value as the DomainName.

Services
--------

List the services which will have a Listener using a port as listed in the ports for it.
Just alike the other modules, we are going to list the services with a set of properties


name
^^^^

The name of the service or ecs.task.family you want to add the listener to

ports
^^^^^

The list of ports for which you would have a listener and want to use the ACM certificate for.
If the protocol was set to HTTP, which is default for ALB, the protocol will automatically be set to **HTTPS**
