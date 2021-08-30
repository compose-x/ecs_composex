.. meta::
    :description: ECS Compose-X AWS Tagging
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Tagging, tagging, resources tags

.. _tags_syntax_reference:

======
x-tags
======

Syntax
======

.. code-block:: yaml
    :caption: x-tags objects definition


    x-tags:
      key: value
      key2: value2


.. code-block:: yaml
    :caption: x-tags list definition


    x-tags:
      - Key: something
        Value: a value


This module helps to set tagging across all the resources and services created in the CloudFormation Stack.
Some specific resources use a slightly different tagging property and these might not all be supported on auto-tagging.
If you notice any missing, please open a new `Feature Request`_

.. _Feature Request: https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=enhancement&template=feature_request.md&title=%5BFR%5D+%3Caws+service%7Cdocker+compose%3E+
