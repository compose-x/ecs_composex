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
          target_tracking:
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
