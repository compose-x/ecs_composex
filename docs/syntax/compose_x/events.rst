
.. meta::
    :description: ECS Compose-X AWS EventsBridge syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS EventsBridge, events, ecs cron job

.. _events_syntax_reference:

==========
x-events
==========

.. code-block:: yaml

    x-events:
      event-logical-name:
        Properties: {}
        Services: {}


Define an AWS EventBride rule to create Scheduled Tasks with the defined services.

.. seealso::

    See to :ref:`how_to_ecs_scheduled_events` for a step by step example.

Services
========

There we define the tasks we want to deploy at specific times or events.

.. code-block:: yaml
    :caption: Services syntax for rules

    Services:
    <service_family_name>:
      TaskCount: <N>
      DeleteDefaultService: True/False (default. False)


TaskCount
-----------

Same property as for ECS Parameters of the `Task Rule target definition`_ itself, this allows you to set a specific number
of tasks.

*Required: Yes.*

.. hint::

    Not using deploy/replicas on purpose, because of the `DeleteDefaultService`_ option

DeleteDefaultService
-----------------------

Custom setting, this allows you to NOT define a ECS Service along with the task, therefore you will only get the TaskDefinition
created.

Properties
==========

You can find all the properties on the `AWS CFN Events Rules definitions`_.

.. note::

    You do not need to define Targets to point to the services defined in docker-compose. Refer to `Services`_ for that.


JSON Schema
============

Model
------

.. jsonschema:: ../../../ecs_composex/events/x-events.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/events/x-events.spec.json

Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/events>`__ to use
as reference for your use-case.

.. _AWS CFN Events Rules definitions: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-events-rule.html
.. _Task Rule target definition: https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutTargets.html
