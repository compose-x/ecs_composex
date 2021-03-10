.. _x_efs_syntax_reference:

=================
x-efs
=================

As described in the :ref:`volumes_syntax_reference` documentation, in order to setup an AWS EFS Filesystem, you can
either use the ECS Plugin definition, which will let ECS Compose-X import and define default settings, or alternatively,
you can define your own settings using **x-efs**.

.. attention::

    For more details around permissions and access to the filesystem, refer to `Filesystem, Access Point and services access`_

Syntax reference
================

.. code-block::

    volumes:
      abcd:
        x-efs:
          Properties: {}
          MacroParameters: {}
          Settings: {}
          Lookup: {}
          Use: <str>

.. hint::

    Even though x-efs is defined at the volumes level, at rendering time, a top level EFS stack will be created to contain
    the various filesystems required to be shared access across services.

Properties
===========

As usual, the Properties supported as equal to the properties you would define in native CloudFormation.
Refer to the `AWS CFN EFS syntax reference`_ for more details.

MacroParameters
===============

However, AWS EFS has evolved since and some very tidy and neat features have emerged since, such as the EFS Access Points.

As it is ECS Compose-X objective to abstract that complexity away from developers but retain the security to high standards,
we have implemented simple feature(s) to automatically enable using features such as IAM Authentication to further control access.

EnforceIamAuth
---------------

.. code-block:: yaml
    :caption: Enable IAM Auth restriction

    volumes:
      abcd:
        x-efs:
          MacroParameters:
            EnforceIamAuth: <True|False>

The purpose of IAM Authentication is to allow applications to authenticate against an EFS Access Point which will allow
for further security configuration, such as, setting UID/GID to use, among others.

But primarily this will allow connection to the EFS using the Task IAM Role as a way to authenticate a specific application
which can then translate into specific files access permissions.

When using IAM Authentication, this also enforces to use TLS between the client and the server, for increased security.

By enabling this feature, an access point will be created specifically for your services in the task definition, along with
the filesystem.

.. attention::

    To use that feature, it is highly recommend to use the `EFS Mount Helper`_

Settings
=========

This might be one rare case where the generic **EnvNames** has no impact, given that the volume name is the only thing
that matters in this particular use-case. ECS Will automatically resolve the DNS name of the target in order to mount
the shared filesystem as a volume to the container.

Subnets
-------

As for other services that require to be created in a VPC to be accessed (for EFS, via `Mount Targets`_), you can
override the default behaviour (for EFS, defaults to the StorageSubnets).

Lookup
=======

As usual, the Plug N' Play aspect of ECS Compose-X to your existing infrastructure is a key concern, therefore, you
can also use ECS Compose-X to identify dynamically AWS EFS which already exists.

.. code-block:: yaml

    volumes:
      abcd:
        x-efs:
          Lookup:
            Tags: []
            RoleArn: <>

Use
====

If you did know your Filesystem ID in AWS EFS, and wanted to just pass it on as the value instead of using Lookup, you can,
either through use or through the original ECS Plugin definition.

.. code-block:: yaml
    :caption: ECS Plugin syntax

    volumes:
      abcd:
        external: true
        name: fs-abcd1234


.. code-block:: yaml
    :caption: ECS ComposeX Syntax

    volumes:
      abcd:
        x-efs:
          Use: fs-abcd1234


Examples
=========

A full example using Bitnami Wordpress image (which requires users permissions etc. to be set) can be found in
`GitHub <https://github.com/compose-x/wordpress-demo>`__


Filesystem, Access Point and services access
=============================================

AWS EFS has a notion of Access Point, which are very well described in the docs and other blog articles on the AWS sites.
In a nutshell, they will allow you to control access to the Filesystem and "proxy" your access so that your services can
set use specific POSIX users and root folders to the filesystem

This comes in to be very important if you are using a shared EFS among multiple tenants (applications, services etc.) and
want to ensure separation for each but not have to spend hours configuring each service clients.

Access point per "container" within the task definition
--------------------------------------------------------

In ECS Compose-X there is only so much that we can understand from the settings set at the volumes level.
Given ECS Compose-X tries to focus as much as possible on security, we have implemented the following:

* If your task definition only has 1 container definition, there is one volume created in the task level, used by containers
* If there is more than one container definition and you defined a different **user** property for the service, a new
    access point is created specifically for that container, added to the task definition.

.. warning::

    Even with 1 access point per container in the task definition, the access remains at the task level for IAM permissions.

.. _AWS CFN EFS syntax reference: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-filesystem.html
.. _Mount Targets: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-mounttarget.html
.. _EFS Mount Helper: https://docs.aws.amazon.com/efs/latest/ug/mounting-fs-mount-helper.html
