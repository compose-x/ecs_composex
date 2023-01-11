
.. _lexicon:

########################
Lexicon & Definitions
########################


Before diving into the examples and getting started, there are a few terms to be familiar to get the most out of the
documentation and examples

CloudFormation / CFN
======================

`The AWS CloudFormation service.`_

In AWS CFN, a template is used in order to create a stack. The Stack will then create the resources etc.
See more details with the `AWS CFN Stack Anatomy`_

------------

.. _family_lexicon:

Service Family
========================

When defining a services in Docker Compose, running `docker-compose up` will start all containers at the same time on the machine running Docker.
When deploying to Amazon Web Services (AWS) Elastic Container Service (ECS) using ECS Compose-X,
each service is represented as its own `Task Definition`_ and Service Definition, and can be managed across multiple hosts.

Sometimes, it is desirable to have more than one container running at the same time, in which case a Family can be used
to group multiple containers into the same Task Definition. To define multiple services from the Docker Compose file to
be part of the same Family, set the `ecs.task.family` label in the deploy configuration.

For example, within ECS Compose-X, setting **x-ray** to true in the service definition automatically adds a sidecar
aws-xray-daemon container as an additional container, of the same Family.


.. hint::

    If not specified via the deploy label ``ecs.task.family``, it uses the service name.

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

------------

Task Definition
===================

The ECS task definition as defined in ECS. This is what determines overall CPU, RAM, docker volumes and source (i.e. EFS)
as well as IAM roles to use.

.. seealso::

    More details can be found in the `AWS Task Definition CFN Syntax`_

------------

Service Definition
====================

The ECS Cluster uses the service definition to create a service based on the task definition.
This service has properties such as the VPC, Subnets, auto-scaling, and other settings that define the deployment.

.. seealso::

    More details can be found in the `AWS Service Definition CFN Syntax`_

------------

services.x-feature
=====================

Extension fields are used to extend the utility of the ECS Compose-X template,
allowing you to customize the behavior of the services in the stack. They are not used by docker-compose, but can
be used to add additional features to the template that docker-compose does not support.

For example, here x-s3 is a top level feature of ECS Compose-X, whereas x-scaling only applies at the `Service Family`_ level.

.. code-block:: yaml

    x-s3:               # x-s3 is a top level definition
      bucket-01: {}

    services:
      nginx:
        image: nginx
        x-scaling:      # This is a service.x- extension
            Range: 1-10

------------

JSON Schema
=============

ECS Compose-X validates the input given to it to maintain the same level of accuracy as Docker Compose,
which utilizes the Compose-Spec JSON schema. This simplifies the code and results in a more straightforward syntax.
The `compose-spec`_ is extended with the additional features in ECS Compose-X.

.. seealso::

    `JSON Schema documentation`_


.. _The AWS CloudFormation service.: https://aws.amazon.com/cloudformation/
.. _AWS CFN Stack Anatomy: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html
.. _AWS Task Definition CFN Syntax: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html
.. _AWS Service Definition CFN Syntax: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-service.html
.. _JSON Schema documentation: https://json-schema.org/
.. _compose-spec: https://github.com/compose-spec/compose-spec
