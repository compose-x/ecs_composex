.. _xray_syntax_reference:

=======
x-xray
=======

This section allows to enable X-Ray to run right next to your container.
It will use the AWS original image for X-Ray Daemon and exposes the ports to the task.

Syntax reference
=================

.. code-block:: yaml

    x-xray: True/False


Example
=======

    services:
      serviceA:
        x-xray: True

.. seealso::

    ecs_composex.ecs.ecs_service#set_xray
