.. meta::
    :description: ECS Compose-X ECR extension
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, security, ECR, repositories, security

.. _composex_ecr_extension:


==================
services.x-ecr
==================

Most companies running applications in AWS use the power of AWS ECR to store their docker images, and most use the
free scan feature to detect security vulnerabilities by scanning the content of the images and match it against CVE
databases.

To validate that the images that we are about to use, ECS Compose-X uses `ECR Scan Reporter`_ as a library to perform
some images securities evaluations.

.. hint::

    Future features to come won't necessarily be related to security.

Syntax Reference
==================

.. code-block::

    services:
      serviceA:
        image: 012345678912.dkr.region.amazonaws.com/repo:tag
        x-ecr:
          VulnerabilitiesScan:
            IgnoreFailure: bool
            TreatFailedAs: str
            Thresholds:
              CRITICAL: number
              HIGH: number
              MEDIUM: number
              LOW: number
            RoleArn: str

IgnoreFailure
--------------

Boolean to indicate that, although you wanted the scan to be evaluated, it won't stop compose-x execution.

*Required*: No

TreatFailedAs
---------------

When the scan status is FAILED (unsupported image for example), allow do define whether that is fine or not.

*Allowed Values*: Success | Failure
*Required*: No

Thresholds
----------

Allows you to define the level for evaluation that you wish to have for stopping the execution.

*Default*: 0 for all 4 levels.
*Required*: No
*Allowed Properties*: CRITICAL, HIGH, MEDIUM, LOW

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
          VulnerabilitiesScan:
            IgnoreFailure: false
            Thresholds:
              CRITICAL: 0
              HIGH: 5
              MEDIUM: 10
              LOW: 10

.. _ECR Scan Reporter: https://ecr-scan-reporter.compose-x.io/
