
.. meta::
    :description: ECS Compose-X AWS SNS syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS SNS, notifications, messages

.. _sns_syntax_reference:

############
x-sns
############

Module to manage SNS Topics that are going to be used by your services or other AWS Resources you define in the compose
files.

.. code-block:: yaml
    :caption: x-sns syntax reference

    x-sns:
      TopicA:
        Properties: {}
        Settings: {}
        Services: {}

Properties
===========

Refer to `AWS SNS Topic Documentation`_ for SNS Topics

.. _AWS SNS Topic Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-sns-topic.html
.. _AWS SNS Subscriptions Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-sns-subscription.html


Lookup
=======

Lookup is currently implemented for SNS topics!


Examples
========

.. literalinclude:: ../../../use-cases/sns/simple_sns.yml
    :language: yaml
    :caption: Create new topics

.. literalinclude:: ../../../use-cases/sns/create_and_lookup.yml
    :language: yaml
    :caption: Create and Lookup SNS topics

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/sns>`__ to use
    as reference for your use-case.
