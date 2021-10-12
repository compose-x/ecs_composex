.. meta::
    :description: ECS Compose-X ACM syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, autoscaling, cloudwatch, alarms, sns, topics

.. _cw_alarms_syntax_reference:

===========
x-alarms
===========

Syntax
=======

.. contents::
    :depth: 2

.. code-block:: yaml
    :caption: Syntax reference

    x-alarms:
      alarm-01:
        Properties: {}
        MacroParameters: {}
        Settings: {}
        Services: []
        Topics: []

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/alarms>`__ to use
    as reference for your use-case.

.. seealso::

    For more structural details, see `JSON Schema`_

Properties
==============

ECS Compose-X will automatically detect whether your properties define an Alarm or a Composite Alarm.

See `AWS CW Alarms definition`_ and `AWS CW Composite Alarms definition`_

.. attention::

    When linking to Services and/or Topics, the OKActions, AlarmActions will be overridden accordingly.

.. attention::

    You can only create new alarms. To use existing alarms with new services would required to modify
    the actions of that alarm, which would be an external change to any IaC.


Linking to x-resources properties
===================================

.. hint::

    This feature only works for **Dimensions** and **Namespace** at the moment. Future versions will add support
    for alarms defined using **Metrics** (mutually exclusive to **Namespace**)

When defining new alarms, you probably want to create these alarms for resources in the compose file, i.e, x-elbv2.

So from the Namespace, x-alarms will then scan resources which were defined in the compose definitions and for the
dimensions you wish to import the value from, interpolate and modify the final CloudFormation template to link automatically
to that resource.

Supported x-resources
-------------------------

* `x-elbv2`_ (requires AWS/ApplicationELB or AWS/NetworkELB as value for Namespace)

x-elbv2
^^^^^^^^^^^

Marker for LB: **x-elbv2::<lb_name>**
Marker for Target Group: **x-elbv2::<lb_name>::<service>::<port>**

.. hint::

    The port is required as you might have multiple targets for the same given service family.


.. literalinclude:: ../../../use-cases/elbv2/create_only_with_alarms.yml
    :language: yaml
    :caption: Example test file (truncated) use-cases/elbv2/create_only_with_alarms.yml
    :lines: 22-25,86-89,106-110,123-


MacroParameters
=================

For x-alarms, MacroParameters is here to help define in a simpler way a composite alarm. More specifically, all you have
to define is the Alarm expression

.. code-block:: yaml

    MacroParameters:
      CompositeExpression: <str>

CompositeExpression
++++++++++++++++++++

String with a logical high level expression of the composite alarm.

.. hint::

    In your expression, use the alarm name as defined in the compose file, not using the **AlarmName** property!
    ECS Compose-X will automatically map to the CFN Alarm being created.

Services
=========

.. code-block:: yaml

    x-alarms:
      kafka-scaling-01:
        Properties: {}
        Services:
          - name: <str>
            access: <str>
            scaling: {} # Service scaling definition

Topics
======

.. code-block:: yaml
    :caption: Topics syntax

    x-alarms:
      alarms-01:
        Properties: {}
        Topics:
          - TopicArn: <str>
            NotifyOn: okay
          - x-sns: <str>
            NotifyOn: all

TopicArn
+++++++++

A string representing the topic ARN. The topic ARN must be valid (will be validated).

x-sns
++++++

Allows you to define a SNS topic that was defined in compose-x files already.
Supports new created topics and topics found via Lookup.

NotifyOn
+++++++++

This allows you to determine whether the messages should be published based on the alarm status.

+-------+---------------+
| Value | Alarm actions |
+=======+===============+
| all   | OKActions     |
|       |               |
|       | AlarmActions  |
+-------+---------------+
| alarm | AlarmActions  |
+-------+---------------+
| okay  | OKActions     |
+-------+---------------+


Examples
=========

.. literalinclude:: ../../../use-cases/alarms/create_only.with_topics.yml
    :language: yaml
    :caption: Alarm with scaling actions for service


.. code-block:: yaml
    :caption: Example CompositeAlarm with MacroParameters

    x-alarms:
      alarm-01:
        Properties {}

      alarm-02:
        Properties: {}

      composite-alarm:
        MacroParameters:
          CompositeExpression: ALARM(alarm-01) and ALARM(alarm-02)

.. hint::

    When the alarms is only for the service, the alarm gets created in the same stack as the service(s).
    When the alarm has both services and topics, the alarms are created in a separate stack.

.. hint::

    When defining a composite alarm, the actions defined in `Services`_ or `Topics`_ are ignored.

JSON Schema
============

.. jsonschema:: ../../../ecs_composex/specs/x-alarms.spec.json

.. literalinclude:: ../../../ecs_composex/specs/x-alarms.spec.json

.. _x-alarms Documentation: https://docs.compose-x.io/syntax/compose_x/alarms.html


.. _AWS CW Alarms definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html
.. _AWS CW Composite Alarms definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudwatch-compositealarm.html
.. _ComparisonOperator: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-comparisonoperator
.. _EvaluationPeriods: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-evaluationperiods
