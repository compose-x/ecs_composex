
.. meta::
    :description: ECS Compose-X FireLens
    :keywords: AWS, ECS, FireLens, FluentBit

.. _x_logging_firelens_syntax_reference:

#############################################
services.x-logging.FireLens
#############################################

.. code-block:: yaml

services:
  service:
    logging:
      driver: str
      options: {}

    x-logging:
      FireLens: {}

.. code-block:: yaml

x-logging:
  FireLens:
    ShortHands:
      ReplaceAwsLogs: bool
    Advanced:
      SourceFile: str
      ParserFiles: []
      EnableApiHeathCheck: bool
      GracePeriod: int
      ComposeXManagedAwsDestinations: {} # ComposeXManagedAwsDestinations
      EnvironmentVariables: {}

.. hint::

    FireLens configurations being numerous, we recommend to look at the examples / test-cases that are published
    on `GitHub <https://github.com/compose-x/compose-x-firelens-examples>`__


Advanced
==============

SourceFile
------------

Allow you to add a custom source file that will be included to the main configuration part of fluent bit


For example, with the following, we ensure to add the pre-build parsers already in the docker image,
and transform the NGINX logs

.. code-block::

    [SERVICE]
        Parsers_File /fluent-bit/parsers/parsers.conf

    [FILTER]
        Name modify
        Match web-firelens*
        Rename ecs_task_arn task_id

    [FILTER]
        Name parser
        Match web-firelens*
        Parser nginx
        Key_Name log
        Reserve_Data True

.. warning::

    Do not use that source file to add `[PARSER]` definitions. Instead, use `ParserFiles`_

ParserFiles
--------------

This allows you to define additional `[PARSER]` that you have configured into separate files, or use the
ones already in the docker image for Fluent Bit.

For example, the following

.. code-block::

    ParserFiles:
      - parser.conf
      - parsers/java.conf

will result into

.. code-block::

    [SERVICE]
        Parsers_File /compose_x_rendered/parser.conf
        Parsers_File parsers/java.conf

In this example, the file ``parser.conf`` exists, and we import the file that the ``log_router_config`` sidecar will
write to disk for fluentbit to use.

However, java.conf does not exist. So we allow it in the configuration, but if the path is incorrect, it might fail.


ComposeXManagedAwsDestinations
---------------------------------

List of pre-defined / managed services by Compose-X that can be used as destination configuration.

At this time, the two supported are

* `FireLensFirehoseManagedDestination`_
* FireLensCloudWatchManagedDestination


FireLensFirehoseManagedDestination
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This section allows to define multiple FireHose definitions if you wish to ship logs to multiple FireHose destinations,
or simply to deliver the logs to FireHose in addition to delivering to another plugin, i.e. CloudWatch
