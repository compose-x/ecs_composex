.. meta::
    :description: ECS Compose-X AWS ECS AutoScaling syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ECS, autoscaling, cpu scaling, memory scaling, ecs scaling

.. _ecs_composex_scaling_syntax_reference:

=========
x-scaling
=========

.. contents::

This section allows to define scaling for the ECS Service.
For SQS Based scaling using step scaling, refer to SQS Documentation.

.. code-block:: yaml

    services:
      serviceA:
        x-scaling:
          Range: "1-10"
          TargetScaling:
            CpuTarget: 80

Range
=====

Range, defines the minimum and maximum number of containers you will have running in the cluster.

.. code-block:: yaml

    #Syntax
    # Range: "<min>-<max>"
    # Example
    Range: "1-21"

.. _xscaling_target_scaling_syntax_refernece:

TargetScaling
==============

Allows you to define target scaling for the service based on CPU/RAM.

.. code-block:: yaml
    :caption: target scaling syntax reference


    x-scaling:
      Range: "1-10"
      TargetScaling:
        CpuTarget: int (will be casted to float)
        MemoryTarget: int (will be casted to float)
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
