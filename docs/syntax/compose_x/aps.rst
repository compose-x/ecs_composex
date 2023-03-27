

.. _prometheus_syntax:

=============================
x-aps - AWS::APS::Workspace
=============================

Module to create/use existing AWS Managed Prometheus workspace(s).

.. code-block:: yaml

    x-aps:
      managed-prometheus-01:
        Properties: {}
        MacroParameters: {}
        Services: {}
        Lookup: {}

Services
=============

ReturnValues
---------------

You can export to environment variables the native `AWS APS Workspace.ReturnValues`_, as per the documentation.

.. tip::

    Non standard output attributes are also available:

    * RemoteWriteUrl: Uses the value for `PrometheusEndpoint`_ and adds ``/api/v1/remote_write`` to the URL.
    * QueryUrl: Uses the value for `PrometheusEndpoint`_ and adds ``/api/v1/query`` to the URL.

    .. attention::

        These are currently only available via ``ReturnValues``, not via ``x-aps::<workspace>::<ReturnValue>`` in environment variables.

MacroParameters
================

CreateNewLogGroup
-------------------

Parameter that can either be a boolean or the Properties for `AWS Logs LogGroup`_
It creates a new Log Group for Prometheus to log information to.


JSON Schema
============

Model
-------

.. jsonschema:: ../../../ecs_composex/aps/x-aps.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/aps/x-aps.spec.json


Test files
============

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/aps>`__ to use
as reference for your use-case.


.. meta::
    :description: ECS Compose-X AWS Managed Prometheus
    :keywords: AWS, ecs, docker compose, prometheus, monitoring, observability

.. _AWS APS Workspace.ReturnValues: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-aps-workspace.html#aws-resource-aps-workspace-return-values
.. _PrometheusEndpoint: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-aps-workspace.html#aws-resource-aps-workspace-return-values
.. _AWS Logs LogGroup: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-logs-loggroup.html
