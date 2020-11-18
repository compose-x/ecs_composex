.. _sns_syntax_reference:

======
x-sns
======

Syntax
======

.. code-block:: yaml
    :caption: x-sns syntax reference


    x-sns:
      Topics:
        TopicA:
          Properties: {}
          Settings: {}
          Services: []
      Subscriptions:
        SubscriptionA:
          Properties: {}
          Settings: {}
          Topics: []


.. warning::

    At this current version, **Subscriptions** are not supported.


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
