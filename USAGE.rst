ECS ComposeX
============

.. contents::

Assumptions
-----------

There are so many ways to do things on AWS especially these days with Containers.
Mostly two ways here regarding how the networking is going to be handled:

* Add a CloudMap to the VPC and register the microservices against the Service Discovery
* Not use CloudMap and use a custom Route53 record that will put an ALB or NLB in front of the service.

Otherwise,

* You are happy with AWS, and **you understand the cost of avoiding vendor locking** - that's my way to say I am using AWS tools, not 3rd parties.
* You want security first and therefore are happy that your containers security groups is going to be as tight as possible.
* You want the flexibility to use EC2 or Fargate and therefore are happy to align the definitions around Fargate requirements (ie. awsvpc network mode)
* You know which service needs access to what resources.

Examples
--------

I cannot provide as many examples as I would like at this stage. I did work on a similar version
of that tool and this was using a rather large docker compose file with 20-ish environment variables per
service and roughly 60 services.

End-to-end of creating the whole stack with SQS, SNS, RDS and then the services was taking about 30 mins.

The examples I have for now are the examples I used to run the tests for this.

Walkthrough
-----------


ECS ComposeX submodules can be used in a standalone fashion. Refer to each submodules specific usage section for more details.

.. note:: I worked to get all modules to work under the same input. Objective is to have a single CLI and pick which modules you want to consider when running.
