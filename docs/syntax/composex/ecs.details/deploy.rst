.. _composex_deploy_extension:

deploy
------

The deploy section allows to set various settings around how the container should be deployed, and what compute resources
are required to run the service.

For more details on the deploy, see `docker documentation for deploy here <https://docs.docker.com/compose/compose-file/#deploy>`_

At the moment, all keys are not supported, mostly due to the way Fargate by nature is expecting settings to be.

resources
"""""""""

The resources is probably what interests most individuals, in setting up how much CPU and RAM should be setup for the service.
I have tried to capture for various exceptions for the RAM settings, as you can find in ecs_composex.ecs.docker_tools.set_memory_to_mb

Once the container definitions are put together, the CPU and RAM requirements are put together. From there, it will automatically
select the closest valid Fargate CPU/RAM combination and set the parameter for the Task definition.

.. important::

    CPUs should be set between 0.25 and 4 to be valid for Fargate, otherwise you will have an error.

.. warning::

    At the moment, I decided to hardcode these values in the CFN template. It is ugly, but pending bigger work to allow
    services merging, after which these will be put into a CFN parameter to allow you to change it on the fly.


replicas
^^^^^^^^

This setting allows you to define how many tasks should be running for a given service.
To make this work, I simply update the MicroserviceCount parameter default value, to keep things configurable.

.. important::::

    It is important for you to know that currently, ECS Does not support restart_policy, so there is no immediate plan
    to support that value.

.. note::

    update_config will be use very soon to support replacement of services using a LB to possibly use CodeDeploy
    Blue/Green deployment.

.. _composex_families_labels_syntax_reference:

labels
^^^^^^^

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
++++++++++++++++

For example, you would have:

.. literalinclude:: ../../../../use-cases/blog.features.yml
    :language: yaml
    :emphasize-lines: 25-26, 68-70, 147-149

.. warning::

    The example above illustrates that you can either use, for deploy labels

    * a list of strings

    * a dictionary

.. _cluster_syntax_reference:


ecs.depends.condition
+++++++++++++++++++++

This label allows to define what condition should this service be monitored under by ECS. Useful when container is set
as a dependency to another.

.. hint::

    Allowed values are : START, SUCCESS, COMPLETE, HEALTHY. By default, sets to START, and if you defined **healthcheck**,
    defaults to HEALTHY.
    See `Dependency reference for more information <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdependency.html>`_
