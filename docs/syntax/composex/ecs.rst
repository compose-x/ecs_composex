.. _services_extensions_syntax_reference:

==========================
x-configs
==========================

This is where developers can leverage the automation implemented in ECS ComposeX to simplify access to their services,
between services themselves and from external sources too.


To define configuration specific to the service and override ECS ComposeX default settings for network configuration,
you can use the native *configs* key of Docker compose.

.. note::

    To define configuration for your service, simply create a new element/dict in the configs element of the YAML file.


.. toctree::
    :caption: deploy

    ecs.details/deploy

:ref:`secrets_syntax_reference`
