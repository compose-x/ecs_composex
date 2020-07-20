.. highlight:: shell

=================
The Why & The How
=================

.. contents::

Introduction
============

`Docker Compose`_ has been around for a long while and enabled developers to perform local integration testing between
their microservices as well as with other dependencies their application have (i.e. a redis or MySQL server).

However, for developers to translate their docker compose file into an AWS infrastructure can be a lot of work. And for
the cloud engineers (or DevOps engineers) it can very quickly become something overwhelming to manage at very large scale
to ensure best-practices are in place, for example, ensuring least privileges access from a service to another.

This is where `ECS ComposeX`_ comes into play.

Translate Docker services into AWS ECS
--------------------------------------

First ECS ComposeX translates the services definition in the docker compose file into the ECS definitions to allow the service to
run on AWS. It will, doing so, create all the necessary elements to ensure a successful and feature rich deployment into ECS.

.. note::

    ECS ComposeX has been built to allow services to run with Fargate or EC2.


Provision other AWS resources your services need
------------------------------------------------

So you have the definitions of your services and they are running on ECS.
But what about these other services that you need for your application to work? DBs, notifications, streams etc.
Are you going to run your MySQL server onto ECS too or are you going to want to use AWS RDS?
How are you going to define the IAM roles and policies for each service? Access Secrets? Configuration settings?

That is the second focus of ECS ComposeX: defining extra sections in the YAML document of your docker compose file, you
can define, for your databases, queues, secrets etc.

ECS ComposeX will parse every single one of these components. These components can exist on their own but what is of interest
is to allow the services to access these.

That is where ECS ComposeX will automatically take care of all of that for you.

For services like SQS or SNS, it will create the IAM policies and assign the permissions to your ECS Task Role so the service
gets access to these via IAM and STS. Credentials will be available through the metadata endpoint, which your SDK will pick
immediately.

For services such as RDS or ElasticCache, it will create the security groups ingress rules as needed, and when applicable,
will handle to generate secrets and expose these via ECS Secrets to your services.

What does ECS ComposeX do differently?
======================================

Where ECS ComposeX distinguishes itself from other tools is embedding security for each service individually,
so that developers only have to connect resources logically together in the same way they would use links between
microservices in their Docker Compose definition. Each microservice needs to explicitly be declared as a consumer of a
resource to get access to it, otherwise it won’t be able to access the resource or other microservices. This is done
simply by using AWS IAM policies or security groups ingress, where applicable. In a future release, ECS ComposeX will
allow using AWS App Mesh for service-to-service communication. This provides the cloud engineers the peace of mind that
the surface of attack to the platform is limited in distributed environments as isolation is achieved for each
microservice individually.

That simplified way to define access between services and resources helps with defining a shared-responsibility model
between application engineers and cloud engineers. Application engineers must know what their application does and how
services interface to each other and to external services. This gives a sense of ownership to the maintainers of the
Docker Compose file that defines the application stack resources and services along with resources access and
permissions.

How does it work?
=================

To do so, ECS ComposeX will use the library called `Troposphere`_ and generate all the CloudFormation templates for it.
These extra resources that you need (RDS, SQS etc.), need to be defined. To keep things simple, you can defined them
in the same way you would do in AWS CloudFormation templates, add these resources to your compose definition.

.. hint::

    x- is ignored by docker-compose when you run it. See `Extensions fields`_

.. note::

    x- and y- are natively defined in the `YAML Specifications`_


Why did I create ECS ComposeX?
==============================

Many companies I have worked with struggle with providing a true cloudy experience to their developers and enable them
to deploy AWS resources in a controlled fashion. And when they do give poweruser/administrator level of permissions to
developers, they usually have not been trained appropriately to understand fundamentals, such as least privileges and
you end up with services which all use the same AWS Access and Secret keys (yes, I witnessed it recently) and these
keys stay around for eternity (seen 1000+ days).

As an AWS Cloud Engineer, this scares the hell out of me and I feel like this is the first thing I need to fix.
As an automation engineer, I wanted a tool that allows developers to keep using Docker compose, as they very often do,
so they can't run their workload on their laptops for quick testing and application testing.

But, "It works on my laptop" is something that in 2020 is simply unacceptable to companies deploying microservices.

Therefore, combining my love for least privileges and therefore IAM instance capability to implement it,
and the need for a tool going these extra miles, I decided to simply go for it.

.. _later on:

A lot of you probably would prefer to use some other tools, such as Terraform.
But I all heartily believe that cloud engineers should use the IaC provided by the Cloud provider.

Third party integrations are coming, including for example the excellent AWS CFN registries where we already see partners
like DataDog provide the ability to create non AWS resources as part of the CFN stack and remove the need for custom made code.


Why am I not using AWS CDK?
==============================

I started this work before AWS CDK came out with any python support, and I am not a developer professionally but I do
love developing, and python is my language of choice.

Troposphere was the obvious choice as the python library to use to build all the CFN templates.
I find the way Troposphere has been built is awesome, the name of the properties are the same as they are in
AWS CloudFormation, which gives a sense of standard to the user, allowing an experience as close to copy-paste as possible.

`Troposphere`_ has a very nice community and is released often. I did a few PRs myself and `Mark Peek`_
is very proactive with PRs, releases come out regularly.


Why not stick to AWS CFN Templates and CFN macros ?
===================================================

I love AWS CFN Macros and I think that it is not enough spoken about. Probably because at start, Fn::Transform was not over
well documented and importing snippets wasn't working all the time as one would have wanted.

I love CFN and I can write templates very easily in YAML or even in JSON. But, typos are a nightmare and it takes a good
IDE configuration to make it easy and viable.

For small templates, it is fine, but with a lot of conditions, references, parameters, imports, it is very easy to mess it up.
And when come nested stacks, it is a huge amount of time spent waiting and hoping nothing wrong happens in a nested stack.

So, using python, I can do all the loops I want, and most importantly, I can make super consistent all the titles for
the various AWS resources that the templates are going to create. If I make a typo somewhere in a title, this typo goes everywhere,
and therefore, AWS CFN is happy to resolve, find, GetAttributes etc from it.

This saves an insane amount of time.

Also, thanks to using Python and with YAML as a common syntax method to write Docker compose files and AWS templates, we
can marry the two very easily.


Implementing least privileges at the heart of ECS ComposeX
===========================================================

One of the most important value add for a team of Cloud/DevOps engineers who have to look after an environment to use
ECS ComposeX is the persistent implementation of best practices:

* All microservices are using different sets of credentials
* All microservices are isolated by default and allowed traffic only when explicitly permitted
* All microservices must be defined as the consumer of a resource (DB, Queue, Table) to be granted access to it.

There have been to many instances of breaches on AWS due to a lack of strict IAM definitions and permissions. Automation
can solve that problem and with ECS ComposeX the effort is to constantly abide by the least privileges access principle.


I want to use EKS. How can I use ECS ComposeX?
==============================================

You could, but only for the IAM part. If you plan on using EKS, I can't recommend enough to use the AWS Service Operator for K8s.
You can refer to this blog https://aws.amazon.com/blogs/opensource/aws-service-operator-kubernetes-available/ to get more details
about it. You will notice a lot of similarities in what ECS ComposeX tries to achieve, but for ECS as opposed to EKS.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`Mark Peek`: https://github.com/markpeek
.. _`AWS ECS CLI`: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_CLI.html
.. _Troposphere: https://github.com/cloudtools/troposphere
.. _Blog: https://blog.ecs-composex.lambda-my-aws.io/
.. _Docker Compose: https://docs.docker.com/compose/
.. _ECS ComposeX: https://github.com/lambda-my-aws/ecs_composex
.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
