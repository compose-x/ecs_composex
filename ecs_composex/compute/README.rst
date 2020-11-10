.. _compute_readme:

=============================
EC2 resources for ECS Cluster
=============================

This module is here to create the compute resources if so chosen instead of using Fargate.
Given that the default it to use AWS Fargate (soon will make it use Fargate Spot as well),
the EC2 resources which by default were provisioned are now optional.

I would only recommend to use EC2 resources over fargate if you need for performances reasons
create backed AMIs which will have a lot of the docker layers that your images and volumes need.

Features
---------

* Creates the ECS Cluster for the deployment of the services to it.
* Creates an IAM Role and Instance profile for potential EC2 hosts
* Creates a Lunch Template using the IAM Role/Instance Profile and Security group
  so if you want to run instances to troubleshoot inside the VPC, it's easy!

Optionally it will also allow you to:

* Create a SpotFleet to run services on top of ECS instances.

The EC2 instances running on Spot/OnDemand will have a configuration that forces the nodes to bootstrap
properly in order to work. If not as this might happen, the instances will "self-destroy" given it
could not bootstrap properly.

You can come up and override the AMI ID if you'd like (has to be in SSM though at the moment) but I can't
recommend enough to just use a vanilla AWS Amazon Linux ECS Optimized. They just work.

CLI Usage
---------

The CLI is here primarily to have an example of the various settings you would need if you wanted to go
and create the Compute resources yourself (EC2, ASG, SpotFleet).

At the moment, the option *--iam-only* is not implemented but soon it will allow you to get the CFN
templates for just the IAM parts if you so wished to.

.. _ec2_compute_design:

The default EC2 configuration
------------------------------

As I mentioned above, this is not going to provision any compute resources (instances) by default.
The configuration is very simple and uses *cfn-init* which must be one of the most underestimated feature
of CloudFormation.

The IAM Profile allows the node to register against the ECS Cluster and only against that one. As you will
soon realize in this project, everything with IAM is done to be least privileges only.


.. note::

    See :ref:`compute_syntax_reference`
