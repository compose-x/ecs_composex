.. meta::
    :description: ECS Compose-X deploy syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, deploy, resources, replicas, scaling

.. _composex_deploy_extension:

===================
services.deploy
===================

The deploy section allows to set various settings around how the container should be deployed, and what compute resources
are required to run the service.

For more details on the deploy, see `docker documentation for deploy here <https://docs.docker.com/compose/compose-file/compose-file-v3/#deploy>`_

The templates rendered will import all settings you set, and within CloudFormation itself, use conditions to rule
out settings that would be incompatible with a specific compute mode, i.e. ``Fargate``

resources
=============

The resources allow you to define the CPU/RAM reservations and limits. In AWS ECS, the CPU only has one attribute, so
ECS Compose-X will **use the highest value of the two if both set**.

Once the container definitions have been generated, the CPU and RAM requirements are added up together.
From there, it will automatically select the closest valid Fargate CPU/RAM combination and set the parameter for the Task.

.. important::

    CPUs should be set between 0.25 and 4 to be valid for Fargate, otherwise you will have an error.
    ECS Compose-X will automatically correct values to fit within all of the containers in the task,
    to the closest values. First evaluates the CPU, then finds the closest value for RAM.

replicas
==========

This setting allows you to define how many tasks should be running for a given service. It will define the initial
``ecs::DesiredCount`` for your service.

.. _composex_families_labels_syntax_reference:

labels
=========

These labels aren't used as per the documentation. They are only used for the service,
but not for the containers themselves.

We leverage that structure to implement simple services flags that will allow users to define settings.

So, here is the tag that will allow you to merge your reverse proxy or waf (if you used a WAF in container) fronting
your web application:

ecs.task.family
----------------

By default, the name of the "family" used is the name of the service. But you can override it with this label.
When you have multiple services in your compose file that you would want to have in the same ECS TaskDefinition/Service,
you can use that label to join two services together.

.. code-block:: yaml

    services:
      backend: # resulting family name: backend
        image: backend

      webapp: # resulting family name: frontend
        deploy:
          labels:
            ecs.task.family: frontend
        expose:
          8000/tcp

      api: # resulting family name: api
        expose:
         - 8080/tcp

      rproxy: # will be used (duplicated) in both frontend and api families
        ports:
         - 80:80/tcp
        deploy:
          labels:
            ecs.task.family: frontend,api # comma delimited list of the families it belongs with


See `ecs.depends.condition`_ to define services priorities for sidecars.

Full example
++++++++++++++

.. literalinclude:: ../../../../use-cases/blog.features.yml
    :language: yaml

.. warning::

    The example above illustrates that you can either use, for deploy labels

    * a list of strings

.. _ecs_task_family_hostname_ref:

ecs.task.family.hostname
---------------------------

This allows to define the hostname (equivalent of services.hostname) but overrides it for the whole ECS Family.

ecs.depends.condition
----------------------

This label allows to define what condition should this service be monitored under by ECS. Useful when container is set
as a dependency to another.

+----------------+-----------------------+
| label          | ecs.depends.condition |
+----------------+-----------------------+
| Allowed Values | * START               |
|                | * SUCCESS             |
|                | * HEALTHY             |
|                | * COMPLETE            |
+----------------+-----------------------+
| Default        | START                 |
+----------------+-----------------------+

.. hint::

    f you defined **healthcheck** on your service, changes to HEALTHY.
    See `Dependency reference for more information`_

ecs.ephemeral.storage
-----------------------

This label allows you to extend the local capacity (ephemeral, which is destroyed after the task is stopped) of storage
beyond the free 20GB coming by default.

+---------+-----------------------+
| label   | ecs.ephemeral.storage |
+---------+-----------------------+
| Minimum | 21                    |
+---------+-----------------------+
| Maximum | 200                   |
+---------+-----------------------+

.. hint::

    The minimum valid value is 21, maximum is 200. If below 21, it is ignored, if above 200, set to 200.
    This feature is only valid when using Fargate.

.. warning::

    This parameter only when using Fargate. This will be ignored when using EC2 or EXTERNAL deployment modes.
    For more storage using EC2, provide more local storage for your EC2 nodes.

.. _ecs_anywhere_compute_platform:

ecs.compute.platform
----------------------

This setting allows you to define which compute platform to deploy your services onto. This is useful if you
have cluster that has a mix of EC2 capacity (default behaviour) and Fargate ones.
This can also allow you to define to deploy your container to ECS Anywhere (using EXTERNAL mode).

+----------------+----------------------+
| label          | ecs.compute.platform |
+----------------+----------------------+
| Allowed Values | * EC2                |
|                | * FARGATE            |
|                | * EXTERNAL           |
+----------------+----------------------+

.. hint::

    By default, ECS Clusters created with ECS Compose-X will use AWS Fargate as the compute platform.

.. hint::

    If you created your cluster without providing any Capacity Providers, Fargate cannot work.
    Compose-X, when using x-cluster.Lookup will attempt to determine whether the Fargate capacity providers
    are present, and if not, override to EC2 **for all services**

.. tip::

    Below two ECS Clusters, one created via CLI without any arguments, the other created in the AWS Console.

    .. code-block:: bash
        :caption: ECS cluster created without capacity providers

        aws ecs create-cluster --cluster-name testing
        {
            "cluster": {
                "clusterArn": "arn:aws:ecs:eu-west-1:2111111111111:cluster/testing",
                "clusterName": "testing",
                "status": "ACTIVE",
                "registeredContainerInstancesCount": 0,
                "runningTasksCount": 0,
                "pendingTasksCount": 0,
                "activeServicesCount": 0,
                "statistics": [],
                "tags": [],
                "settings": [
                    {
                        "name": "containerInsights",
                        "value": "enabled"
                    }
                ],
                "capacityProviders": [],
                "defaultCapacityProviderStrategy": []
            }
        }

    .. code-block:: json
        :caption: Cluster created in the AWS Console which automatically adds FARGATE providers

        [
          {
            "clusterArn": "arn:aws:ecs:eu-west-1:211111111111:cluster/testinginconsole",
            "clusterName": "testinginconsole",
            "status": "ACTIVE",
            "registeredContainerInstancesCount": 0,
            "runningTasksCount": 0,
            "pendingTasksCount": 0,
            "activeServicesCount": 0,
            "statistics": [],
            "tags": [],
            "settings": [
              {
                "name": "containerInsights",
                "value": "enabled"
              }
            ],
            "capacityProviders": [
              "FARGATE_SPOT",
              "FARGATE"
            ],
            "defaultCapacityProviderStrategy": []
          }
        ]

    .. seealso::

        `Add CapacityProviders via the CLI`_

.. _Dependency reference for more information: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdependency.html
.. _Add CapacityProviders via the CLI: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-capacity-providers.html#fargate-capacity-providers-existing-cluster
