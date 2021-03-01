.. meta::
    :description: ECS Compose-X deploy syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, deploy, resources, replicas, scaling

.. _composex_deploy_extension:

deploy
=======

The deploy section allows to set various settings around how the container should be deployed, and what compute resources
are required to run the service.

For more details on the deploy, see `docker documentation for deploy here <https://docs.docker.com/compose/compose-file/compose-file-v3/#deploy>`_

At the moment, all keys are not supported, mostly due to the way Fargate by nature is expecting settings to be.

resources
-----------

The resources allow you to define the CPU/RAM reservations and limits. In AWS ECS, the CPU only has one attribute, so
ECS Compose-X will **use the highest value of the two if both set**.

Once the container definitions have been generated, the CPU and RAM requirements are added up together.
From there, it will automatically select the closest valid Fargate CPU/RAM combination and set the parameter for the Task.

.. important::

    CPUs should be set between 0.25 and 4 to be valid for Fargate, otherwise you will have an error.

replicas
+++++++++

This setting allows you to define how many tasks should be running for a given service.
The value is used to define **MicroserviceCount**.

.. _composex_families_labels_syntax_reference:

labels
+++++++

These labels aren't used for much in native Docker compose as per the documentation. They are only used for the service,
but not for the containers themselves. Which is great for us, as we can then leverage that structure to implement a
merge of services.

In AWS ECS, a Task definition is a group of one or more containers which are going to be running as a one task.
The most usual use-case for this, is with web applications, which need to have a reverse proxy (ie. nginx) in front
of the actual application. But also, if you used the *use_xray* option, you realized that ECS ComposeX automatically
adds the x-ray-daemon sidecar. Equally, when we implement AppMesh, we will also have another side-car container for this.

So, here is the tag that will allow you to merge your reverse proxy or waf (if you used a WAF in container) fronting
your web application:

ecs.task.family
^^^^^^^^^^^^^^^

For example, you would have:

.. literalinclude:: ../../../../use-cases/blog.features.yml
    :language: yaml
    :emphasize-lines: 30-31, 83-85

.. warning::

    The example above illustrates that you can either use, for deploy labels

    * a list of strings

    * a dictionary

ecs.depends.condition
^^^^^^^^^^^^^^^^^^^^^^

This label allows to define what condition should this service be monitored under by ECS. Useful when container is set
as a dependency to another.

.. hint::

    Allowed values are : START, SUCCESS, COMPLETE, HEALTHY. By default, sets to START, and if you defined **healthcheck**,
    defaults to HEALTHY.
    See `Dependency reference for more information`_

.. _Dependency reference for more information: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdependency.html
