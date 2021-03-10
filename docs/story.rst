.. meta::
    :description: ECS Compose-X background
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, story, background

.. highlight:: shell


Philosophy
=============

CloudFormation is awesome, the documentation is excellent and the format easy. So ECS Compose-X wants to keep the format
of resources Properties as close to the orignal as possible as well as making it easier as well, just alike resources
like **AWS::Serverless::Function** which will create all the resources around your Lambda Function as well as the function.

Trying to implement DevOps starting with developers
----------------------------------------------------

Whilst this is something that can be used by AWS Cloud Engineers tomorrow to deploy applications on ECS on the behalf
of their developers, the purpose of ECS Compose-X is to enable developers with a simplistic and familiar syntax that
takes away the need to be an AWS Expert. If tomorrow developers using Compose-X feel comfortable to deploy services
by themselves, I would be able to stop hand-holding them all the time and focus on other areas.

Community focused
------------------

Any new Feature Request submitted by someone other than myself will get their request prioritized to try address their
use-cases as quickly as possible.

`Submit your Feature Request here <https://github.com/lambda-my-aws/ecs_composex/issues/new/choose>`_

Ensure things work
------------------

It takes an insane amount of time to test everything as, generating CFN templates is easy, testing that everything
works end-to-end is a completely different thing.

I will always do my best to ensure that any new feature is tested end-to-end, but shall anything slip through the cracks,
please feel free to report your errors `here <https://github.com/lambda-my-aws/ecs_composex/issues/new/choose>`_


Provision other AWS resources your services need
------------------------------------------------

So you have the definitions of your services and they are running on ECS.
But what about these other services that you need for your application to work? DBs, notifications, streams etc.
Are you going to run your MySQL server onto ECS too or are you going to want to use AWS RDS?
How are you going to define the IAM roles and policies for each service? Access Secrets? Configuration settings?

That is the second focus of ECS Compose-X: defining extra sections in the YAML document of your docker compose file, you
can define, for your databases, queues, secrets etc.

ECS Compose-X will parse every single one of these components. These components can exist on their own but what is of interest
is to allow the services to access these.

That is where ECS Compose-X will automatically take care of all of that for you.

For services like SQS or SNS, it will create the IAM policies and assign the permissions to your ECS Task Role so the service
gets access to these via IAM and STS. Credentials will be available through the metadata endpoint, which your SDK will pick
immediately.

For services such as RDS or ElasticCache, it will create the security groups ingress rules as needed, and when applicable,
will handle to generate secrets and expose these via ECS Secrets to your services.

How does it work?
-----------------

To do so, ECS Compose-X will use the library called `Troposphere`_ and generate all the CloudFormation templates for it.
These extra resources that you need (RDS, SQS etc.), need to be defined. To keep things simple, you can defined them
in the same way you would do in AWS CloudFormation templates, add these resources to your compose definition.

.. hint::

    x- is ignored by docker-compose when you run it. See `Extensions fields`_

.. note::

    x- and y- are natively defined in the `YAML Specifications`_


What does ECS Compose-X do differently? Long version
=======================================================

Where ECS Compose-X distinguishes itself from other tools is embedding security for each service individually,
so that developers only have to connect resources logically together in the same way they would use links between
microservices in their Docker Compose definition.

Each microservice needs to explicitly be declared as a consumer of a resource to get access to it,
otherwise it won’t be able to access the resource or other microservices.

This is achieved simply by using AWS IAM policies or security groups ingress, where applicable.

That simplified way to define access between services and resources helps with defining a shared-responsibility model
between application engineers and cloud engineers:

Application engineers must know what their application does and how services interface to each other and to external services.
This gives a sense of ownership to the developers of the infrastructure for the services,
via the definitions in the Docker Compose file that defines the application stack resources and services along with resources access and
permissions.


Why did I create ECS Compose-X?
=================================

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

ECS Compose-X was started before AWS CDK came out with any python support, and python was the language of choice for this
project.

Therefore, Troposphere was the obvious choice as the python library to use to build all the CFN templates.
The way Troposphere has been built is simple and clear, the name of the properties are the same as they are in
AWS CloudFormation, which gives a sense of standard to the user, allowing an experience as close to copy-paste as possible.

`Troposphere`_ has a very strong community and has wide set of AWS services support.
The community is active and other AWS Projects members are directly involved in the day-to-day life of the project.

In CDK, all the properties you have to set for a CFN resource have been renamed, Troposphere kept the same name definition
for the resources properties. To me, this is a very valuable thing, not to have to map CFN properties to a language specific
one.


Implementing least privileges at the heart of ECS Compose-X
===========================================================

One of the most important value add for a team of Cloud/DevOps engineers who have to look after an environment to use
ECS Compose-X is the persistent implementation of best practices:

* All microservices are using different sets of credentials
* All microservices are isolated by default and allowed traffic only when explicitly permitted
* All microservices must be defined as the consumer of a resource (DB, Queue, Table) to be granted access to it.

There have been to many instances of breaches on AWS due to a lack of strict IAM definitions and permissions. Automation
can solve that problem and with ECS Compose-X the effort is to constantly abide by the least privileges access principle.


.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`Mark Peek`: https://github.com/markpeek
.. _`AWS ECS CLI`: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_CLI.html
.. _Troposphere: https://github.com/cloudtools/troposphere
.. _Blog: https://blog.composex.io/
.. _Docker Compose: https://docs.docker.com/compose/
.. _ECS Compose-X: https://github.com/lambda-my-aws/ecs_composex
.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
