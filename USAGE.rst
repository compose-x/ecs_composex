========================
ECS Composex - Examples
========================

.. contents::

ecs_composex
============

Create everything
-----------------

.. code-block:: bash

    ecs_composex --create-vpc --create-cluster -f /path/to/docker/file -o /tmp/stack.json
    aws cloudformation create-stack --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
        --template-body file://outputs/test.json  \
        --stack-name toto

Create VPC and use existing ECS Cluster
----------------------------------------

.. code-block:: bash

    ecs_composex --create-vpc --cluster-name test1 -f /path/to/docker/file -o /tmp/stack.json
    aws cloudformation create-stack --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
        --template-body file://outputs/test.json \
        --parameters file://outputs/test.params.json \
        --stack-name toto

Use existing VPC and existing cluster
--------------------------------------

.. code-block:: bash

    ecs_composex -f tests/services_with_queues.yml  -o outputs/test.json --cluster-name test1 \
        --public-subnets subnet-074987ef81402e6ca,subnet-00f7f9c1fc66ae3d3,subnet-03756ada536dfcd1e \
        --app-subnets subnet-095cb471f64ef12d4,subnet-0d60458a6867c6014,subnet-003c6a3c3934bfea2 \
        --storage-subnets subnet-0300645f9f93a4cf9,subnet-021d10b3cb6c94741,subnet-0c2e6c55baf9040cc \
        --vpc-id vpc-078f14e333ad0269c \
        --map ns-hox7np22c6kere6u

    aws cloudformation create-stack --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
        --template-body file://outputs/test.json  \
        --parameters file://outputs/test.params.json \
        --stack-name toto


ecs_composex-vpc
=================

This CLI is to create just a VPC on its own. That way, if you intend to do a lot of testing, this will save you some
time each time you deploy a new Cluster/Services in standalone. As in the example above, you can refer to the resources
IDs simply by looking at the outputs of the VPC stack this will create

.. code-block:: bash

    # Creates VPC with a single NAT for all application subnets
    ecs_composex-vpc -o outputs/vpc.json --single-nat
    # Create VPC with a NAT for each Appsubnet based on their AZ
     ecs_composex-vpc -o outputs/vpc.json

    aws cloudformation create-stack --template-body file://outputs/vpc.json --stack-name vpcalone

ecs_composex-sqs
================

Similar to the VPC specific CLI, this allows you to create the templates for each SQS Queues shall you only
want to use ECS ComposeX to make your life easy with SQS configuration.

.. code-block:: bash

    ecs_composex-sqs -f /path/to/docker/compose.yml -o outputs/sqs.json
