.. _events_syntax_reference:

==========
x-events
==========

This extension allows you to define an AWS EventBride rule to stop start services at specific times
of the day or based on specific events.

Properties
==========

You can find all the properties on the `AWS CFN Events Rules definitions`_.

.. note::

    You do not need to define Targets to point to the services defined in docker-compose. Refer to `Services`_ for that.

MacroParameters
================

No specific parameters at this time!


Settings
========

No specific settings at this time!

Services
========

There we define the tasks we want to deploy at specific times or events.

.. code-block:: yaml
    :caption: Services syntax for rules

    name: service_name
    TaskCount: <N>
    DeleteDefaultService: True/False (default. False)

name
""""

Here we want to define the name of the **family** we want to use for trigger. If the service is not defined as part of a
specific family, you can use the service name itself.

.. seealso::

    .. :ref:`composex_deploy_extension`

*Required: Yes.*

TaskCount
"""""""""

Same property as for ECS Parameters of the `Task Rule target definition`_ itself, this allows you to set a specific number
of tasks.

*Required: Yes.*

.. hint::

    Not using deploy/replicas on purpose, because of the `DeleteDefaultService`_ option

DeleteDefaultService
"""""""""""""""""""""

Custom setting, this allows you to NOT define a ECS Service along with the task, therefore you will only get the TaskDefinition
created.

.. _AWS CFN Events Rules definitions: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-events-rule.html
.. _Task Rule target definition: https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutTargets.html
