
.. meta::
    :description: ECS Compose-X AWS ECS AutoScaling syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ECS, autoscaling, cpu scaling, memory scaling, ecs scaling

.. _ecs_composex_scaling_syntax_reference:

======================
services.x-scaling
======================

.. code-block:: yaml

    services:
      serviceA:
        x-scaling:
          Range: str
          ScheduledActions: []
          TargetScaling:
            CpuTarget: float
            RamTarget: float

Range
=====

Range, defines the minimum and maximum number of containers you will have running in the cluster.

.. code-block:: yaml

    #Syntax
    # Range: "<min>-<max>"
    # Example
    Range: "1-21"

.. _xscaling_scheduledactions:

ScheduledActions
==================

The ScheduledActions is a list of ScheduledActions as created and defined by `AwsCommunity::ApplicationAutoscaling::ScheduledAction`_
allowing to create scheduled autoscaling activities to change the MinCapacity and MaxCapacity of your ECS Service.

This allows for great flexibility and costs savings to ensure you always get all the capacity you need when you need it,
and rely at the same time on otherwise defined scaling policies.

Example
--------

In the following example, Monday to Friday, for 1h, we change the scaling max & min.

.. code-block:: yaml

    services:
      my-service:
        x-scaling:
          Range: 1-10
          ScheduledActions:
            - Timezone: Europe/London
              Schedule: cron(45 2 ? * MON-FRIN)
              ScheduledActionName: Scale.Up
              ScalableTargetAction:
                MinCapacity: 2
                MaxCapacity: 4
              MacroParameters:
                AddServiceName: true
            - Timezone: Europe/London
              Schedule: cron(45 3 ? * MON-FRIN)
              ScheduledActionName: Scale.Down
              ScalableTargetAction:
                MinCapacity: 1
                MaxCapacity: 2

.. _xscaling_target_scaling_syntax_refernece:

TargetScaling
==============

Allows you to define target scaling for the service based on CPU/RAM.

.. code-block:: yaml
    :caption: target scaling syntax reference


    x-scaling:
      Range: "1-10"
      TargetScaling:
        CpuTarget: number (percentage, i.e. 75.0)
        MemoryTarget: number (percentage, i.e. 80.0)
        ScaleInCooldown: int (ie. 60)
        ScaleOutCooldown: int (ie. 60)
        DisableScaleIn: boolean (True/False)


CpuTarget / RamTarget
-----------------------

Defines the CPU **percentage** that we want the service to be under. ECS will automatically create and adapt alarms to
scale the service in/out so long as the average CPU usage remains beneath that value.

.. attention::

    Note that setting both should not be set at the same time, as you might end up into a racing condition.

ScaleInCooldown / ScaleOutCooldown
-----------------------------------

This allows you to define the Cooldown between scaling activities in order to limit drastic changes.

.. hint::

    These are set only for the CPU and RAM targets, no impact on other scaling such as SQS.

DisableScaleIn
--------------

Default: False

Same as the original Property in the CFN definition, this will deny a service to scale in after it has scaled-out for
applications that do not support to scale-in.


.. hint::

    If you define multiple services within the same **family**, the lowest value for CPU/RAM and highest for scale in/out
    are used in order to minimize the impact and focus on the weakest point.

.. tip::

    For SQS Based scaling using step scaling, refer to SQS :ref:`sqs_scaling_reference` Documentation.


JSON Schema
===========

Model
------

.. jsonschema:: ../../../../ecs_composex/specs/services.x-scaling.spec.json

Definition
-----------

.. literalinclude:: ../../../../ecs_composex/specs/services.x-scaling.spec.json
    :language: json

.. _AwsCommunity::ApplicationAutoscaling::ScheduledAction: https://github.com/aws-cloudformation/community-registry-extensions/tree/main/resources/ApplicationAutoscaling_ScheduledAction
