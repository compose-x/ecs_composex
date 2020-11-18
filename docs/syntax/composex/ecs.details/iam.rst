.. _x_configs_iam_syntax_reference:

======
x-iam
======

.. contents::

This section is the entrypoint to further extension of IAM definition for the IAM roles created throughout.

boundary
========

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
========

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
================

Allows you to add additional managed policies. You can specify the full ARN or just a string for the name / path of the
policy. If will resolve into the same regexp as for `boundary`_
