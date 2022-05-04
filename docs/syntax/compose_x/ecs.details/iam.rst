
.. meta::
    :description: ECS Compose-X AWS IAM syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS IAM, least-privileges, permissions, iam

.. _x_iam_syntax_reference:

==================
services.x-iam
==================

.. code-block:: yaml

    x-iam:
      Policies: []
      PermissionsBoundary: str
      ManagedPolicyArns: []

This section is the entrypoint to further extension of IAM definition for the IAM roles created throughout.


PermissionsBoundary
======================

This key represents an IAM policy (name or ARN) that needs to be added to the IAM roles in order to represent the IAM
Permissions Boundary.

.. tip::

    if you specify ony the name, ie. **containers**, this will resolve into
    **arn:${AWS::Partition}:iam::${AWS::AccountId}:policy/containers**


.. code-block:: yaml
    :caption: PermissionsBoundary example

    services:
      serviceA:
        image: nginx
        x-iam:
          PermissionsBoundary: containers
      serviceB:
        image: redis
        x-iam:
          PermissionsBoundary: arn:aws:iam::aws:policy/PowerUserAccess

.. note::

    You can either provide a full policy arn, or just the name of your policy.
    The validation regexp is:

    .. code-block:: python

        r"((^([a-zA-Z0-9-_.\/]+)$)|(^(arn:aws:iam::(aws|[0-9]{12}):policy\/)[a-zA-Z0-9-_.\/]+$))"

Policies
==========

Allows you to define additional IAM policies.
Follows the same pattern as CFN IAM Policies

.. code-block:: yaml


    x-iam:
      Policies:
          - PolicyName: somenewpolicy
            PolicyDocument:
              Version: "2012-10-17"
              Statement:
                - Effect: Allow
                  Action:
                    - ec2:Describe*
                  Resource:
                    - "*"
                  Sid: "AllowDescribeAll"

.. tip::

    This is equivalent to *x-aws-role* if you used the ECS Plugin.

ManagedPolicyArns
==================

Allows you to add additional managed policies. You can specify the full ARN or just a string for the name / path of the
policy. If will resolve into the same regexp as for `PermissionsBoundary`_

.. tip::

    If you used the ECS Plugin from docker before, this is equivalent to *x-aws-policies*

.. hint::

    You can also use the Docker ECS-Plugin **x-aws-iam** extension fields with ECS ComposeX

.. code-block:: yaml
    :caption: ManagedPolicies example

    services:
      serviceA:
        x-iam:
          ManagedPolicyArns:
            - arn:aws:iam::aws:policy/Administrator # AWS Managed Policy
            - developer                             # User Managed Policy

JSON Schema
=============

Model
---------
.. jsonschema:: ../../../../ecs_composex/specs/services.x-iam.spec.json

Definition
-----------

.. literalinclude:: ../../../../ecs_composex/specs/services.x-iam.spec.json
    :language: json
