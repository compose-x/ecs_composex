=============
AWS Kinesis
=============

AWS Kinesis is a highly durable, highly scalable messages streaming service.
I cannot start to list the number of use-cases where AWS Kinesis can be used and its incredible performance and scalability.

For more details, head to `AWS Kinesis page`_ for features, use-cases and pricing.


Integration with ComposeX
=========================

As for all the other modules, this extension in ComposeX with the Docker-Compose extension field allows you to define
new Kinesis streams (or Lookup existing ones) to connect your services defined in your docker-compose file to it.

IAM permissions
---------------

.. literalinclude:: ../../ecs_composex/kinesis/kinesis_perms.json
    :language: JSON
    :caption: IAM permissions pre-defined for your services.


.. _AWS Kinesis page: https://aws.amazon.com/kinesis/
