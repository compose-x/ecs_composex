
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
      EnableApiHeathCheck: bool
      GracePeriod: int
      ComposeXManagedAwsDestinations: {} # ComposeXManagedAwsDestinations
      EnvironmentVariables: {}

.. hint::

    FireLens configurations being numerous, we recommend to look at the examples / test-cases that are published
    on `GitHub <https://github.com/compose-x/compose-x-firelens-examples>`__


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
