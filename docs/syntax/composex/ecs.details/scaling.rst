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
          range: "1-10"
          target_tracking:
            cpu_target: 80

range
=====

Range, defines the minimum and maximum number of containers you will have running in the cluster.

.. code-block:: yaml

    #Syntax
    # range: "<min>-<max>"
    # Example
    range: "1-21"


allow_zero
==========

Boolean to allow the scaling to go all the way down to 0 containers running. Perfect for cost savings and get to pure
event driven architecture.

.. hint::

    If you set the range minimum above 0 and then set allow_zero to True, it will override the minimum value.

.. _xscaling_target_scaling_syntax_refernece:

target_scaling
==============

Allows you to define target scaling for the service based on CPU/RAM.

target scaling syntax reference
--------------------------------

.. code-block:: yaml


    x-scaling:
      range: "1-10"
      target_scaling:
        cpu_target: int (will be casted to float)
        memory_target: int (will be casted to float)
        scale_in_cooldown: int (ie. 60)
        scale_out_cooldown: int (ie. 60)
        disable_scale_in: boolean (True/False)
