.. _elbv2_syntax_reference:

=======
x-elbv2
=======

This module is a rework in-depth of the previous **lb_type** property in **x-configs** aimed to allow a lot more detailed
configuration, and in the future, to allow more detailed LB configuration, to allow pointing to Lambda or use Cognito
to authenticate etc.

Syntax
======

.. code-block:: yaml

    x-elbv2:
      lbA:
        Properties: {}
        Settings:
          timeout_seconds: int
          desync_mitigation_mode: str
          drop_invalid_header_fields: bool
          http2: bool
          cross_zone: bool
        Services:
          - name: str
            protocol: str
            port: int
            healthcheck: str




Properties
==========

These as for every other x-resource is to re-use the similar properties as described in the CFN definition of a `Load
Balancer v2 <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html>`_.

Although once again, the aim of ECS ComposeX is to take a lot of the complexity away from the user.
The only two properties that are really necessary to set are

* `Scheme`_
* `Type`_

.. hint::

    For Application Load Balancers, a new security group will be created automatically.
    Subnets are selected automatically based on the scheme you indicated.
    If selected a public NLB, the IP addressed will automatically be provisioned too.

Settings
========

Once again in an effort of making configuration shorter and easier, here as the options you can simply indicate.

* timeout_seconds: 60
* desync_mitigation_mode: defensive
* drop_invalid_header_fields: True
* http2: False
* cross_zone: True

These settings are just a shorter notation for the `LB Attributes`_


MacroParameters
================

.. _load_balancers_ingress_syntax_ref:

Ingress
-------

Similar syntax as for ECS Services Ingress, allow you to define Ingress (only applies to ALB).

.. code-block:: yaml
    :caption: Ingress Syntax

    Ingress:
      ExtSources: []
      AwsSources: []

.. code-block:: yaml
    :caption: ExtSources syntax

    ExtSources:
      - Name: str (if any non alphanumeric character set, will be deleted)
        Description: str
        Ipv4: str

.. code-block:: yaml
    :caption: AwsSources syntax

    AwsSources:
      - Type: SecurityGroup|PrefixList (str)
        Id: sg-[a-z0-9]+|pl-[a-z0-9]+

Services
========

This follows the regular pattern of having the name of the service and access, only this time in a slightly different format.
The services represent the `Target Group`_ definition of your service. Once again, in an attempt to keep things simple,
you do not have to indicate all of the settings exactly as CFN does.

The Targets will automatically be pointing towards the ECS Service tasks.

name
----

Given that you can now re-use one of the service in the docker-compose file multiple times for multiple ECS Services
in multiple Task definitions, and ECS to ELBv2 supports to route traffic to a specific container in the task definition,
you have to indicate the service name in the following format

.. code-block::

    # name: <family_name>:<service_name>
    name: youtoo:app01
    name: app03:app03

.. hint::

    If you service is not associated to a family via deploy labels, the family name is the same as the service name.


protocol
--------

The Target Group protocol


port
^^^^

The port of the target to send the traffic to

.. hint::

    This port is the port used by the Target Group to send traffic to, which can be different to your healthcheck port.


healthcheck
-----------

The healthcheck properties can be defined in the same fashion as defined in the `Target Group`_ definition.
However, it is also possible to shorten the syntax into a simple string


.. code-block:: yaml

    (port:protocol)(:healthy_count:unhealthy_count:intervals:timeout)?(:path:http_codes)?

.. note::

    The last part, for path and HTTP codes, is only valid for ALB


Listeners
=========

You can define in a very simple way your `Listener definition`_ and cross-reference other resources, here, the services
and ACM certificates you might be creating.

It has its own set of properties, custom to ECS ComposeX.

The following properties are identical to the original CFN definition.

* `Port <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-listener.html#cfn-elasticloadbalancingv2-listener-port>`_
* `Protocol <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-listener.html#cfn-elasticloadbalancingv2-listener-protocol>`_
* `SslPolicy <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-listener.html#cfn-elasticloadbalancingv2-listener-sslpolicy>`_
* `Certificates <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-listener.html#cfn-elasticloadbalancingv2-listener-certificates>`_


.. hint::

    For certificates, you can also use **x-acm** to refer to an ACM certificate you are creating with this stack.
    It will automatically import the Certificate ARN and map it once created.

.. hint::

    You can re-use the same ACM certificate defined in x-acm for multiple listeners. Make sure to have all the Alt. Subjects you need!

.. warning::

    The certificate ARN must be valid when set, however, we are not checking that it actually exists.(yet)


ECS ComposeX custom properties
==============================

Targets
-------

List of targets to send the requests to.

.. code-block:: yaml

    name: <service_name> ie. app03:app03


This represents the targets and simultaneously the Listener Rules to apply so that you can point to multiple services
at once and implement these rules.



Examples
========

.. literalinclude:: ../../../use-cases/elbv2/create_only.yml
    :language: yaml


.. _LB Attributes: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-loadbalancerattributes
.. _Scheme: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme
.. _Type: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-type
.. _Target Group: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html
.. _Listener definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-listener.html
