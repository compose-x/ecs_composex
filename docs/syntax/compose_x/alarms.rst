.. meta::
    :description: ECS Compose-X ACM syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, autoscaling, cloudwatch, alarms, sns, topics

.. _cw_alarms_syntax_reference:

===========
x-alarms
===========

.. code-block:: yaml
    :caption: Syntax reference

    x-alarms:
      alarm-01:
        Properties: {}
        Settings: {}
        Services: []
        Topics: []


Properties
==============

See `AWS CW Alarams definition`_

.. attention::

    When linking to Services and/or Topics, the OKActions, AlarmActions will be overridden accordingly.

.. attention::

    You can only create new alarms. To use existing alarms with new services would required to modify
    the actions of that alarm, which would be an external change to any IaC.


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


.. hint::

    When the alarms is only for the service, the alarm gets created in the same stack as the service(s).
    When the alarm has both services and topics, the alarms are created in a separate stack.

.. _AWS CW Alarams definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html
.. _ComparisonOperator: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-comparisonoperator
.. _EvaluationPeriods: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-evaluationperiods
