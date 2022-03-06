
.. _compatibility_matrix:

===========================
Compatibility Matrix
===========================

The compatibility matrices are here to help you identify how ECS Compose-X integrates with Docker Compose, with AWS and
more specifically AWS ECS. Although AWS ECS definitions allow to match very closely docker-compose specifications,
some features are simply not available, or not compatible, based on the environment you want to run the services,
for example, on EC2/ECS instances vs Fargate vs ECS Anywhere.

If there were any compatibility or feature mistake, please do not hesitate to `open an issue`_ in the GitHub repository.

.. toctree::
    :titlesonly:
    :maxdepth: 1

    compatibility/aws_ecs
    compatibility/docker_compose
    compatibility/docker_ecs_plugin
    compatibility/iam_sam

.. _open an issue: https://github.com/compose-x/ecs_composex/issues
