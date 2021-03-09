.. meta::
    :description: ECS Compose-X ACM syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ACM, SSL Certificates

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

.. code-block::

    x-alarms:
      kafka-scaling-01:
        Properties: {}
        Services:
          - name: app01
            access: RA
            scaling: {} # Service scaling definition

Examples
=========

.. literalinclude:: ../../../use-cases/alarms/create_only.yml
    :language: yaml
    :caption: Alarm with scaling actions for service


.. _AWS CW Alarams definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html
.. _ComparisonOperator: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-comparisonoperator
.. _EvaluationPeriods: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-evaluationperiods
