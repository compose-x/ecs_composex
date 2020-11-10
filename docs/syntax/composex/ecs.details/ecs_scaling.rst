.. _ecs_composex_scaling_syntax_reference:

scaling
-------

This section allows to define scaling for the ECS Service.
For SQS Based scaling using step scaling, refer to SQS Documentation.

.. code-block:: yaml

    services:
      serviceA:
        x-configs:
          scaling:
            range: "1-10"
            target_tracking:
                cpu_target: 80

range
"""""

Range, defines the minimum and maximum number of containers you will have running in the cluster.

.. code-block:: yaml

    #Syntax
    # range: "<min>-<max>"
    # Example
    range: "1-21"


allow_zero
"""""""""""

Boolean to allow the scaling to go all the way down to 0 containers running. Perfect for cost savings and get to pure
event driven architecture.

.. hint::

    If you set the range minimum above 0 and then set allow_zero to True, it will override the minimum value.

target_scaling
""""""""""""""

Allows you to define target scaling for the service based on CPU/RAM.

.. code-block:: yaml

    x-configs:
      target_scaling:
        range: "1-10"
        cpu_target: 75
        memory_target: 80

Available options:

.. code-block:: yaml

    x-configs:
      scaling:
          range: "1-10"
          target_scaling:
            cpu_target: int (will be casted to fload)
            memory_target: int (will be casted to float)
            scale_in_cooldown: int (ie. 60)
            scale_out_cooldown: int (ie. 60)
            disable_scale_in: boolean (True/False)
