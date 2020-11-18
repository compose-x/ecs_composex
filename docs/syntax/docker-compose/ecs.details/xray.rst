.. _xray_syntax_reference:

=====
xray
=====

This section allows to enable X-Ray to run right next to your container.
It will use the AWS original image for X-Ray Daemon and exposes the ports to the task.

Example:

.. code-block:: yaml

    x-configs:
      composex:
        xray:
          enabled: true

    services:
      serviceA:
        x-configs:
          xray:
            enabled: True

.. seealso::

    ecs_composex.ecs.ecs_service#set_xray
