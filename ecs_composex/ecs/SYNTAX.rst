.. _services_syntax_reference:

x-configs & services reference
==============================

This is where we try to re-use as much as possible the docker compose (v3) reference as much as possible.
For the definition of the services, you can simply use the already existing Docker compose definition for your services.
However, there are only a limited number of settings that are today working:

* `ports <https://docs.docker.com/compose/compose-file/#ports>`_
* `environment <https://docs.docker.com/compose/compose-file/#environment>`_
* `links <https://docs.docker.com/compose/compose-file/#links>`_
* `depends_on <https://docs.docker.com/compose/compose-file/#environment>`_
* `x-configs`_
* `deploy`_

.. seealso::

    `Docker Compose file reference <https://docs.docker.com/compose/compose-file>`_

ECS ComposeX configurations
---------------------------

This is where developers can leverage the automation implemented in ECS ComposeX to simplify access to their services,
between services themselves and from external sources too.


To define configuration specific to the service and override ECS ComposeX default settings for network configuration,
you can use the native *configs* key of Docker compose.

.. note::

    To define configuration for your service, simply create a new element/dict in the configs element of the YAML file.

x-configs
---------

Configs is a section natively supported by docker-compose. The sections allows you to define generic settings for all
services, and apply it to services.

The way the definition of settings has been implemented is to go from the generic to the specific:

* 1. x-configs -> composex
* 2. x-configs -> service name
* 3. x-services -> service

.. hint::

    If a setting is set in both step 1 and step 3 for example, the value that will be kept is the value from step 3.

network
^^^^^^^

This is a top section describing the network configuration in play for the service.

Subkeys of the section:

*   `ext_sources`_

*   `is_public`_

*   `lb_type`_

*   `use_cloudmap`_

*   `healthcheck`_

.. code-block:: yaml

    services:
      serviceA:
        image: image
        links: []
        ports:
        - 80:80
        x-configs:
          network:
        lb_type: application
            ext_sources: []
            healthcheck: {}


ext_sources
"""""""""""

This allows you to define specific ingress control from external sources to your environment. For example, if you have
to whitelist IP addresses that are to be allowed communication to the services, you can list these, and indicate their
name which will be shown in the EC2 security group description of the ingress rule.

.. code-block:: yaml

    x-configs:
      app01:
        network:
          ext_sources:
            - ipv4: 0.0.0.0/0
              protocol: tcp
              source_name: all
            - ipv4: 1.1.1.1/32
              protocol: icmp
              source_name: CloudFlareDNS

.. note::

    Future feature is to allow to input a security group ID and the remote account ID to allow ingress traffic from
    a security group owned by another of your account (or 3rd party).
    This feature was implemented before AWS released AWS EC2 PrefixLists.
    It will be migrated to PrefixLists eventually.


is_public
"""""""""

boolean to indicate whether or not the service should be accessible publicly. If set to true, the *load balancer* associated
to the service will be made public.

lb_type
"""""""

When using a load-balancer to reach to the service, specify the Load Balancer type.
Accepted values:

* network
* application

use_cloudmap
"""""""""""""

This indicates whether or not you want the service to be added to your VPC CloudMap instance. if set to true, it will
automatically register the service to the discovery instance.

healthcheck
"""""""""""""

At this time, this does not replace the docker compose native functionality of healthcheck. It is a simplified expression of it
which is used for cloudmap or the load-balancer to register the targets.

.. note::

    This is used for network healthchecks, not service healthcheck


iam
^^^^

This section is the entrypoint to further extension of IAM definition for the IAM roles created throughout.

boundary
""""""""

This key represents an IAM policy (name or ARN) that needs to be added to the IAM roles in order to represent the IAM
Permissions Boundary.

.. note::

    You can either provide a full policy arn, or just the name of your policy.
    The validation regexp is:

    .. code-block:: python

        r"((^([a-zA-Z0-9-_.\/]+)$)|(^(arn:aws:iam::(aws|[0-9]{12}):policy\/)[a-zA-Z0-9-_.\/]+$))"

Examples:

.. code-block:: yaml

    services:
      serviceA:
        image: nginx
        x-configs:
          iam:
            boundary: containers
      serviceB:
        image: redis
        x-configs:
          iam:
            boundary: arn:aws:iam::aws:policy/PowerUserAccess

.. note::

    if you specify ony the name, ie. containers, this will resolve into arn:${partition}:iam::${accountId}:policy/containers

policies
"""""""""

Allows you to define additional IAM policies.
Follows the same pattern as CFN IAM Policies

.. code-block:: yaml

    x-configs:
      iam:
        policies:
          - name: somenewpolicy
            document:
              Version: "2012-10-17"
              Statement:
                - Effect: Allow
                  Action:
                    - ec2:Describe*
                  Resource:
                    - "*"
                  Sid: "AllowDescribeAll"

managed_policies
""""""""""""""""

Allows you to add additional managed policies. You can specify the full ARN or just a string for the name / path of the
policy. If will resolve into the same regexp as for `boundary`_


xray
^^^^^
This section allows to enable X-Ray to run right next to your container.
It will use the AWS original image for X-Ray Daemon and exposes the ports to the task.

Example:

.. code-block:: yaml

    x-configs:
      composex:
        xray:
          enabled: true

    services:
      serviceA:
        x-configs:
          xray:
            enabled: True

.. seealso::

    ecs_composex.ecs.ecs_service#set_xray

deploy
------

The deploy section allows to set various settings around how the container should be deployed, and what compute resources
are required to run the service.

For more details on the deploy, see `docker documentation for deploy here <https://docs.docker.com/compose/compose-file/#deploy>`_

At the moment, all keys are not supported, mostly due to the way Fargate by nature is expecting settings to be.

resources
^^^^^^^^^^

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

**ecs.task.family**

For example, you would have:

.. literalinclude:: ../use-cases/blog.yml
    :language: yaml
    :emphasize-lines: 25-26, 45-46

.. warning::

    The example above illustrates that you can either use, for deploy labels

    * a list of strings

    * a dictionary

.. _cluster_syntax_reference:

x-cluster
==========

This section allows you to define how you would like the ECS Cluster to be configured.
It also allows you to define `Lookup` to use an existing ECS Cluster.


Properties
----------

Refer to the `AWS CFN reference for ECS Cluster`_

.. code-block:: yaml
    :caption: Override default settings

    x-cluster:
      Properties:
        CapacityProviders:
          - FARGATE
          - FARGATE_SPOT
        ClusterName: spotalltheway
        DefaultCapacityProviderStrategy:
          - CapacityProvider: FARGATE_SPOT
            Weight: 4
            Base: 2
          - CapacityProvider: FARGATE
            Weight: 1

Lookup
------

Allows you to enter the name of an existing ECS Cluster that you want to deploy your services to.

.. code-block:: yaml
    :caption: Lookup existing cluster example.

    x-cluster:
      Lookup: mycluster


.. warning::

    If the cluster name is not found, by default, a new cluster will be created with the default settings.

Use
----

This key allows you to set a cluster to use, that you do not wish to lookup, you just know the name you want to use.
(Useful for multi-account where you can't lookup cross-account).


.. _AWS CFN reference for ECS Cluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-cluster.html
