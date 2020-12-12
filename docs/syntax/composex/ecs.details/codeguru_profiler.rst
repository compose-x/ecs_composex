.. _codeguru_profiler_syntax_reference:

======================
x-codeguru-profiler
======================

Enables to use or create an existing/a new CodeProfiling group for your service.

Unlike most of the resources attachments, this is not done at the "family" level but at the service
level, as it might not be wanted to profile every single container in the task.

x-codeguru-profiler is a service/task level setting which offers a 1:1 mapping between your application
and the profiler.

.. hint::

    Using ECS ComposeX, this automatically adds an Environment variable to your container,
    **AWS_CODEGURU_PROFILER_GROUP_ARN** with the ARN of the newly created Profiling Group.

Syntax reference / Examples
==============================

I wanted to make it easy for people to use as well as being flexible and support all CFN definition.


.. code-block:: yaml
    :caption: Syntax for setting pre-defined codeprifiling group without creating a new one.

    x-codeguru-profiler: name (str)


.. code-block:: yaml
    :caption: Create a new CodeProfiling group with default settings.

    x-codeguru-profiler: True|False (bool)

.. code-block:: yaml
    :caption: Properties as defined in AWS CFN for ProflingGroup

    x-codeguru-profiler:
      AgentPermissions: Json
      AnomalyDetectionNotificationConfiguration:
        - Channel
      ComputePlatform: String
      ProfilingGroupName: String
      Tags:
        - Tag


.. seealso::

    `AWS CFN definition for CodeGuru profiling group <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-codeguruprofiler-profilinggroup.html>`__

.. note::

    When you define the properties, in case you already had principals, it will still automatically
    add the **IAM Task Role** to the list of Principals that should publish to the profiling group.
