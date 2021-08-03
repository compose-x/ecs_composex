.. meta::
    :description: ECS Compose-X ECR extension
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, security, ECR, repositories, security

.. _composex_ecr_extension:


==================
services.x-ecr
==================

Syntax Reference
==================

.. code-block::

    services:
      serviceA:
        image: 012345678912.dkr.region.amazonaws.com/repo:tag
        x-ecr:
          InterpolateWithDigest: bool
          VulnerabilitiesScan:
            IgnoreFailure: bool
            TreatFailedAs: str
            Thresholds:
              CRITICAL: number
              HIGH: number
              MEDIUM: number
              LOW: number
            RoleArn: str

InterpolateWithDigest
=====================

When the image comes from ECR, we can very easily identify the image digest (sha256) for it and use that instead of a tag.
However not as human user friendly, this allows to always point to the same image regardless of tags change.

+----------+---------+
| Type     | Boolean |
+----------+---------+
| Default  | False   |
+----------+---------+
| Required | False   |
+----------+---------+


VulnerabilitiesScan
====================

Most companies running applications in AWS use the power of AWS ECR to store their docker images, and most use the
free scan feature to detect security vulnerabilities by scanning the content of the images and match it against CVE
databases.

To validate that the images that we are about to use, ECS Compose-X uses `ECR Scan Reporter`_ as a library to perform
some images securities evaluations.

+----------+--------+
| Type     | Object |
+----------+--------+
| Default  | None   |
+----------+--------+
| Required | False  |
+----------+--------+

IgnoreFailure
--------------

Boolean to indicate that, although you wanted the scan to be evaluated, it won't stop compose-x execution.

+----------+---------+
| Type     | Boolean |
+----------+---------+
| Default  | True    |
+----------+---------+
| Required | False   |
+----------+---------+

TreatFailedAs
---------------

When the scan status is FAILED (unsupported image for example), allow do define whether that is fine or not.

+----------------+-----------+
| Type           | Boolean   |
+----------------+-----------+
| Default        | Failure   |
+----------------+-----------+
| Required       | False     |
+----------------+-----------+
| Allowed Values | * Success |
|                | * Failure |
+----------------+-----------+

Thresholds
----------

Allows you to define the level for evaluation that you wish to have for stopping the execution.

+--------------------+-------------+
| Type               | Object      |
+--------------------+-------------+
| Default            | CRITICAL: 0 |
|                    | HIGH: 0     |
|                    | MEDIUM: 0   |
|                    | LOW: 0      |
+--------------------+-------------+
| Required           | False       |
+--------------------+-------------+
| Allowed Attributes | * CRITICAL  |
|                    | * HIGH      |
|                    | * MEDIUM    |
|                    | * LOW       |
+--------------------+-------------+

RoleArn
--------

.. warning:: use with caution

This allows you to give a specific IAM role for probing ECR if the repository is shared across accounts.

Examples
=========

.. code-block:: yaml

    services:
      grafana:
        x-ecr:
          InterpolateWithDigest: true
          VulnerabilitiesScan:
            IgnoreFailure: false
            Thresholds:
              CRITICAL: 0
              HIGH: 5
              MEDIUM: 10
              LOW: 10

.. _ECR Scan Reporter: https://ecr-scan-reporter.compose-x.io/
