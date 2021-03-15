.. meta::
    :description: ECS Compose-X AWS Cloudwatch alarm
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, alarms, monitoring

.. _service_alarms_syntax_reference:

===================
services.x-alarms
===================

*This section describes the service level alarms that will automatically monitor the ECS Service*

.. code-block:: yaml
    :caption: Service level x-alarms reference

    services:
      app01:
        x-alarms:
          Predefined:
            HighCpuUsageAndMaxScaledOut:
              Topics: []                    # Similar to other x-alarms settings
              Settings: {}                  # Input values override.


Predefined alarms
=================

Common Settings
++++++++++++++++

Note that the following properties can be set to override defaults.
It will only update the "Primary" alarm when alarms are composite.

+----------------------+---------+
| Setting              | Default |
+======================+=========+
| `DatapointsToAlarm`_ | 10      |
+----------------------+---------+
| `EvaluationPeriods`_ | 5       |
+----------------------+---------+
| `Period`_            | 60      |
+----------------------+---------+

.. attention::

    Define some scaling range to allow scaling out
    The alarms below will only be active if there are scaling rules defined.


HighCpuUsageAndMaxScaledOut
++++++++++++++++++++++++++++

+------------------+---------------+----------+------------------------------+
| Setting name     | Default Value | Primary? | Comment                      |
+==================+===============+==========+==============================+
| CPUUtilization   | 75            | Y        | Percentage, float            |
+------------------+---------------+----------+------------------------------+
| RunningTaskCount | MAX()         | N        | Count, int.                  |
|                  |               |          | Default goes to max value of |
|                  |               |          |                              |
|                  |               |          | x-scaling.Range              |
+------------------+---------------+----------+------------------------------+

This rule will trigger an alert when the CPUUtilization of a given service will go over the threshold and the tasks
count is equal to the max scaling capacity (or otherwise overriden value).

.. code-block:: yaml
    :caption: Example at 50% CPU usage and override to 4 tasks.

    - Name: HighCpuUsageAndMaxScaledOut
      Settings:
        CPUUtilization: 50             # In percent
        RunningTaskCount: 4            # Number of tasks to evaluate against.


HighRamUsageAndMaxScaledOut
++++++++++++++++++++++++++++

+-------------------+---------------+----------+------------------------------+
| Setting name      | Default Value | Primary? | Comment                      |
+===================+===============+==========+==============================+
| MemoryUtilization | 75            | Y        | Percentage, float            |
+-------------------+---------------+----------+------------------------------+
| RunningTaskCount  | MAX()         | N        | Count, int.                  |
|                   |               |          | Default goes to max value of |
|                   |               |          |                              |
|                   |               |          | x-scaling.Range              |
+-------------------+---------------+----------+------------------------------+

This rule will trigger an alert when the CPUUtilization of a given service will go over the threshold and the tasks
count is equal to the max scaling capacity (or otherwise overriden value).

.. code-block:: yaml
    :caption: Example at 50% CPU usage and override to 4 tasks.

    - Name: HighRamUsageAndMaxScaledOut
      Settings:
        MemoryUtilization: 50          # In percent
        RunningTaskCount: 4            # Number of tasks to evaluate against.



A little bit of philosophy behind alarms
=========================================

I love alarms, but one should only have alarms that do something relevant to the business criticality impact.
Alerting for the sake of alerting might actually cause you more work due. Equally, rules with too aggressive thresholds
will more often than not end up in false positives.

For example, CPU High usage alarms are useless if they do not either trigger an activity or response, such as autoscaling.
You are paying for the whole 100% of your CPU and if you are not on a burstable instance, you want to use as much as possible of it
to make the value worth. Now, high CPU usage on burstable instances **is** a big deal and you want to do something to avoid
throttling.

So as much as alarms are valuable, you should always try to have ones that will action a corrective fix, automated wherever
possible, and if not possible, alert people so risks get mitigated.

.. _DatapointsToAlarm: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarm-datapointstoalarm
.. _EvaluationPeriods: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-evaluationperiods
.. _Period: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cw-alarm.html#cfn-cloudwatch-alarms-period
