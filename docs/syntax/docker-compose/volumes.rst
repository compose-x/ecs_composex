.. _volumes_syntax_reference:

===================
volumes
===================

This section covers the integration compatibility with docker-compose volumes into AWS ECS.

.. seealso::

    `docker-compose volumes`_
    `docker-compose services volumes`_

Understand Local volumes vs shared volumes vs persistent volumes
=================================================================

In docker world, one can create docker volumes and attach these to the containers.

As very well synthesized in the `tmpfs`_ documentation page, we have

.. code-block:: text

    Volumes and bind mounts let you share files between the host machine and container so that you can persist data even after the container is stopped.

    If you’re running Docker on Linux, you have a third option: tmpfs mounts. When you create a container with a tmpfs mount, the container can create files outside the container’s writable layer.

    As opposed to volumes and bind mounts, a tmpfs mount is temporary, and only persisted in the host memory. When the container stops, the tmpfs mount is removed, and files written there won’t be persisted.

In AWS ECS you can use all 3 modes, although, tmpfs is not supported when deploying containers with AWS Fargate, as the host
might be shared with other customers, this could create a surface of attack between containers.

Also, it is worth noting that in AWS Fargate, you cannot use the **bind** mounts from the host: again, shared host, this could
create a surface of attack from one account to another.

But, that does not mean that in AWS Fargate you cannot create additional volumes outside of your image layers.
In fact, AWS Fargate 1.4.0 comes with some encrypted storage for your tasks among other features.

.. seealso::

    `AWS Fargate 1.4.0 announcement`_

Implementation in the AWS + Docker ECS Plugin
==============================================

The ECS Plugin which allows you to define, in a similar way to ECS Compose-X, your volumes, is of the opinion
that any volume you would create is going to be a shared persistent volume using AWS EFS.

As you can see in `these examples <https://docs.docker.com/cloud/ecs-compose-examples/#volumes>`__, you can either leave things by default or define some EFS equivalent properties
to define your volumes.

.. seealso::

    `docker - ecs - volumes syntax reference`_

Implementation in ECS Compose-X
================================

To maintain compatibility with the ECS Plugin, if you did specify that the driver should be **nfs** or **efs** (although this is not
a supported network driver!), ECS Compose-X will create for you a new FS etc. allowing your containers to connect.

However, by default, ECS Compose-X will follow the behaviour described in the `docker-compose volumes`_ reference, which is
to respect the **driver** and **driver_opts** settings.

Define a volume for the task only
----------------------------------

Although you cannot create a tmpfs in AWS Fargate, you might for consistency with your local development, define a volume just
to mount to a specific path.

As per the `docker-compose volumes`_ reference, we could have the following

.. code-block:: yaml

    services:
      service-01:
        volumes:
          # Just specify a path and let the Engine create a volume
          - /var/lib/mysql

There what ECS Compose-X will do is to create in the task definition a new volume using the **local** driver **volume** type,
and assign that to the container definition in the task definition specifically.

Define a shared volume between tasks
-------------------------------------

Alternatively, and this is where the Docker ECS Plugin and ECS Compose-X differ, is in the use of the **volumes** top-level
instruction: unless specified otherwise, the volume will be treated as a local but shared volume.


.. code-block:: yaml

    volumes:
      shared-volume:

    services:
      serviceA:
        volumes:
          - shared-volume:/mnt/shared:rw

      serviceB:
        volumes:
          - source: shared-volume
            target: /mnt/shared
            read_only: false
            type: volume

In the above example, we would get a volume created and mounted to both containers.

Define a shared volume using AWS EFS
-------------------------------------

This is where ECS ComposeX merges back with the Docker ECS Plugin syntax: you can use the same syntax as defined by the
Docker ECS Plugin, for example

Using the ECS Plugin syntax reference
""""""""""""""""""""""""""""""""""""""

.. code-block:: yaml

    services:
      test:
        image: my-app
        volumes:
          - db-data:/app/data
    volumes:
      db-data:
        driver_opts:
            backup_policy: ENABLED
            lifecycle_policy: AFTER_30_DAYS
            performance_mode: maxIO
            throughput_mode: provisioned
            provisioned_throughput: 1024


If you were to use that definition in your compose file with ECS Compose-X, a new EFS will be created with the settings
above, along with all the necessary settings for it.

Using the ECS Compose-X specific reference
"""""""""""""""""""""""""""""""""""""""""""

As usual, you can also define in ECS Compose-X a more comprehensive set of parameters to better define what you want to
achieve, using the **x-efs** key.

To go into more details about using **x-efs**, refer to :ref:`x_efs_syntax_reference`


.. _docker-compose volumes: https://docs.docker.com/compose/compose-file/compose-file-v3/#volume-configuration-reference
.. _docker-compose services volumes: https://docs.docker.com/compose/compose-file/compose-file-v3/#volumes
.. _tmpfs: https://docs.docker.com/storage/tmpfs/
.. _AWS Fargate 1.4.0 announcement: https://aws.amazon.com/about-aws/whats-new/2020/04/aws-fargate-launches-platform-version-14/
.. _docker - ecs - volumes syntax reference: https://docs.docker.com/cloud/ecs-integration/#volumes
