ECS ComposeX aims to make life easy to take your application to AWS ECS, with using AWS Fargate as the primary
focus (still, allows to run on EC2 should you need to).

AWS AppMesh integration
=======================

AWS AppMesh is a service mesh which allows you to define how services talk to each other at an application L7) level,
and optionally, TCP (layer 4) level. It is extremely powerful


Since the beginning of the project, we have been using AWS Cloud Map to create a private DNS Hosted Zone linked to the
VPC created at the same time. This allowed us to very simply register into the PHZ (private hosted zone) via Service
Discovery.

We are going to use these entries to make a 1-1 mapping between our services defined in the *services* section of the
docker-compose file and the *nodes* listed in the *x-appmesh* section.

AppMesh uses envoy as a side-car proxy that will capture our services packets and route these to their defined backends.
Using AWS AppMesh empowers developers to declare how services are supposed to communicate together, what to do in case
of errors, and administrators can define whether or not the traffic between all the components should be done using TLS
termination end-to-end, to ensure no man-in-the-middle attacks could happen.

The syntax for AppMesh in ECS ComposeX is a mix of Istio, Envoy and AWS AppMesh definitions.

.. seealso::

    :ref:`appmesh_syntax_reference`


Services autoscaling integration
=================================

You can now define scaling for your ECS Services using
* CPU / RAM Target Tracking scaling
* SQS Messages (visible) depth with step scaling.

For example, we want to scale our front-end based on CPU usage and our backend, dealing with queues, based on messages
numbers.

.. code-block::

    services:
      frontend:
        ports:
          - 80:80
        image: my-nginx
        deploy:
          replicas: 2 # by default I want 2 containers
        x-configs:
          scaling:
            range: "1-10" # 1 to 10 containers to deploy for the service
            target_scaling:
              cpu_target: 80 # Means 80% average for all containers in the service.
      backend:
        image: my-worker
        deploy:
          replicas: 1  # Initially I want 1 container running to make sure everything is working
        x-configs:
          scaling:
            range: "0-10" # I can have between 0 to 10 containers. 0 because I am happy not paying when nothing to do

    x-sqs:
      jobs-queue:
        Properties: {}
        Settings: {}
        Services:
          - name: frontend
            access: RWMessages
          - name: backend
            access: RWMessages
            scaling:
              steps:
                - lower_bound: 0
                  upper_bound: 10
                  count: 1
                - lower_bound: 10
                  upper_bound: 20
                  count: 2
                - lower_bound: 20
                  count: 21

As you can see we defined scaling for SQS only on the backend, as we don't need to scale the frontend based on that.
Also we set the count for final step to 21, which is higher than the range indicated.

Our frontend will be managed by ECS itself which will be ensuring that the average CPU usage across the service remains under 80%.

.. hint::

    In composex, you must define a generic range first, and if you override it in the scaling, it will take the highest count of all scaling policies.

.. note::

    Scaling with target tracking based on ELBv2 metrics is coming too.


Fargate CPU/RAM auto configuration
==================================

When you want to create services on ECS, you first need to create a Task Definition. Among the IAM permissions and the
network configuration, the Task definition also defines how much CPU and RAM you want to have available **for all your
containers** in the task.

If you have only one service, you might as well just not put any limits at the **Container Definition** level, and let
it use all the available CPU and RAM defined in the **Task Definition**.

.. hint::

    The Task definition CPU and RAM is the maximum CPU and RAM that your containers will be able to use.
    The amount of CPU and RAM in AWS Fargate is what determines how much you are paying.


But when you start to add side-cars, such as Envoy, X-Ray, or your WAF, your reverse-proxy, you want to start setting
how much CPU and RAM these containers can use out of the Task Definition.

In docker-compose (or with swarm), you already have the ability to define the CPU limits and reservations you want to
give to each individual service in the compose file.

To help having to know the different CPU/RAM settings supported by AWS Fargate, ECS ComposeX, if defined, will automatically
use the limits and reservations configuration set in your Docker compose file, and determine what is the closest
CPU/RAM configuration that will allow your services to run into.

.. hint::

    Setting at least the reservation values so your containers are guaranteed some capacity in case
    other containers get to use more resources than expected.

.. seealso::

    `deploy <https://docs.docker.com/compose/compose-file/#deploy>`_ reference.

We have the following example:

.. literalinclude:: ../use-cases/blog.yml
    :language: yaml
    :emphasize-lines: 18-24, 18-44

We have CPU and RAM limits set for **both limits and reservations**. So we know that we can use the limits, add them up,
and this will indicate us our CPU configuration.

.. hint::

    In docker compose, you indicate the CPU as a portion of vCPU. A value of 1.0 means 1024 cycles, or 1vCPU.
    A value of 0.25 equals to 256 cycles, which equivals to .25 of a vCPU.

We get:
* 0.75 vCPU (limits)
* 192MB of RAM.

The closest configuration for Fargate that will cater for the amount of vCPU, is 1024. With 512 only, we **could** run
low in cpu cycles.

So then, from there, we know that Fargate will allow for a minimum of 2GB of RAM. So our CPU/RAM configuration will be
**1024 CPU cycles and 2048MB of RAM**.

Now, let's say we know that our rproxy (NGINX based) will only need .1 CPU at most and 128M of RAM, and we want to make
sure that the application container, does not take all the CPU and RAM away from it, but also that it should not go over
these limits.

So we are going to set these limits for the rproxy container.

.. hint::

    If you do not set the reservations, the container could potentially free compute resources to the benefit of others,
    but at the risk of having none available.

Now, let's say we know our application will use a minimum of 256M, and up to .25 of a CPU.

Let's count:
* .1 vCPU (limit+reservation) and .25 (reservation). We get 0.35vCPU.
* 128MB RAM (limit+reservation) and 256M (reservation), We get 284MB.

The closest configuration for Fargate is .5vCPU and 1024MG of RAM. But, also, our application container can use up to
1024-128 = 896MB of RAM, as we did not set a limit. For some applications where you are not totally sure of the RAM you
might need, this is a good way to keep for free space, just in case.

.. note::

    Chances are, if you are using so low CPU/RAM for your microservice, you might be running it in AWS Lambda!

.. hint::

    You might think that for the CPU you need, ie. 1vCPU, which means you need at least 2GB of RAM for the appropriate
    Fargate profile, is a lot of RAM wasted.

    However, in this configuration, the CPU represents ~80% of the costs (29.5$+6.5$=36$).

Multiple services, one microservice
====================================

Regularly developers will build locally multiple services which are aimed to work together as a group. And sometimes,
these services have such low latency requirements and dependency on each other, that they are best executed together.

In our example before, where we use NGINX to implement webserver logic, configuration and security, and leverage the
power of a purpose-built software, as opposed to re-implement all that logic directly in your application, we might
to run these two together.

On your workstation, when you run *docker-compose up*, it obviously is going to run it all locally. However, by default,
these are defined as individual services.

To allow multiple services to be merged into a single **Task Definition**, and still treat your docker images separately,
you can use a specific label that **ECS ComposeX** will recognize to group services into what we called a **family**.

ECS already has a notion of *family*, so I thought, we should use that naming to group services logically.

The deploy labels are ignored on a container level, therefore, none of these tags will show when you deploy the services.

.. hint::

    The labels can be either a list of strings, or a "document" (dictionary).

Here is an example where we use the label, both as a string (**requires the `=` to be present to define key/value) and
a dictionary. The family for this case is **app01**

.. literalinclude:: ../use-cases/blog-all-features.yml
    :language: yaml
    :emphasize-lines: 25-26, 45-46

But then you might wonder, how come are the permissions going to work for the services?

Remember, the permissions are set at the **Task definition** level. So any container within that service, will get the
same permissions.

**However**, for the database as an example, which creates a Secret in AWS Secrets Manager, which we would then expose
to the service with the *Secrets* attribute of the **Container Definition**, ECS ComposeX will specifically add that
secret to that container only.
Equally, for the services linked to SQS queues or SNS topics (etc.), the environment variable providing with the ARN of
the resource, will also only expose the value to the container set specifically.

In case you wanted to allow an entire *family* of services to get access to the resources, you can also give, as the
service name in the definition, the name of one of your families defined via the labels.

For example,

.. code-block:: yaml

    services:
      worker01:
        image: worker01
        deploy:
          labels:
            ecs.task.family: app01

      worker02:
        image: worker02
        deploy:
          labels:
            ecs.task.family: app01

    x-sqs:
      Queue01:
        Properties: {}
        Services:
          - name: app01
            access: RWMessages

ACM Certificates auto-create for public services
================================================

AWS CloudFormation now supports to auto-validate the Certificate by adding on your behalf the CNAME validation entry
into your Route53 hosted zone.

.. seealso::

    :ref:`acm_syntax_reference`
