
.. _lexicon:

=============
Lexicon
=============


Before diving into the examples and getting started, there are a few terms to be familiar to get the most out of the
documentation and examples

CloudFormation / CFN
======================

`The AWS CloudFormation service.`_

In AWS CFN, a template is used in order to create a stack. The Stack will then create the resources etc.
See more details with the `AWS CFN Stack Anatomy`_


.. _family_lexicon:

Service Family
========================

When defining a services in docker-compose, and you run **docker-compose up**, all the containers are running all at the
same time on the machine running docker for you. When you deploy to AWS ECS via ECS Compose-X, each service is then
its own `Task Definition`_ and `Service Definition`_ and are managed separately, across - potentially - multiple hosts etc.

Sometimes one want to have more than one container running at the same time, although in your docker-compose file they
are defined as individual services.

A **Family** is what allows you to group multiple containers into the same `Task Definition`_ and therefore.

Typically, when you set **x-ray: true** in your service definition, ECS Compose-X automatically adds a sidecar, the
aws-xray-daemon container, as an additional container, of the same "Family" definition.

To define more than one service defined in docker-compose to be part of the same family, simply set the deploy label
**ecs.task.family**.

.. hint::

    If not specified, the "family name" uses the service name.

For example, below, we indicate that nginx should be part of the "kafdrop" family. The ECS Task Definition will therefore
have the settings for the nginx service and the kafdrop service, into one.

.. code-block:: yaml

    services:
      nginx:
        image: nginx
        deploy:
          labels:
            ecs.task.family: kafdrop

        depends_on:
          - kafdrop

      kafdrop:
        image: kafdrop

.. tip::

    You can link the same service to more than one service should the configuration be identical

    .. code-block:: yaml

        services:
          nginx:
            image: nginx
            deploy:
              labels:
                ecs.task.family: kafdrop,grafana # nginx is re-used as-is in both families

          kafdrop:
            image: kafdrop

          grafana:
            image: grafana


In the x-elbv2 module, the services listed require to indicate both the **Family** and the **service/container** to send
traffic to, as the ELBv2 can send traffic to either. Some other features might also require to specify the **family:service**
combination at times.

Otherwise for IAM and most modules, pointing to the service for permissions/access prefers the family name.

Task Definition
===================

The ECS task definition as defined in ECS. This is what determines overall CPU, RAM, docker volumes and source (i.e. EFS)
as well as IAM roles to use.

.. seealso::

    More details can be found in the `AWS Task Definition CFN Syntax`_

Service Definition
====================

The service definitions is what is used in the ECS Cluster to create the service, based on a task definition.
This will set the network properties (VPC, Subnets etc), auto-scaling and otherwise represents the deployment as a service
of the task definition.

.. seealso::

    More details can be found in the `AWS Service Definition CFN Syntax`_

services.x-feature
=====================

In ECS Compose-X, extension fields are used to define properties ignore by docker-compose when running commands, but that
we can then use to extend the utility of the template with.

When in the documentation, is referred a feature as **service.x-**, this means that this is an extension field that is
set inside the service definition.

For example, here x-s3 is a top level feature of ECS Compose-X, whereas x-scaling only applies at the level of the service.
.
.. code-block:: yaml

    x-s3:       # x-s3 is a top level definition
      bucket-01: {}

    services:
      nginx:
        image: nginx
        x-scaling:      # This is a service.x- extension
          Range: 1-10


JSON Schema
=============

Docker Compose uses the Compose-Spec JSON schema to ensure that the input of the syntax of the input to docker-compose file is correct.
To keep with the same level of validation, ECS Compose-X also validates the input given to it to make sure that the input
processed is correct. This removes a lot of conditional verification on the input itself and allows for a lighter code and
much clearer syntax to use.

The compose-spec original extension field is extended with the ECS Compose-X definitions for its features.

.. seealso::

    `JSON Schema documentation`_


.. _The AWS CloudFormation service.: https://aws.amazon.com/cloudformation/
.. _AWS CFN Stack Anatomy: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html
.. _AWS Task Definition CFN Syntax: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html
.. _AWS Service Definition CFN Syntax: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-service.html
.. _JSON Schema documentation: https://json-schema.org/
