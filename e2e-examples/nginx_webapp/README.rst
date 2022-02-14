
.. meta::
    :description: ECS Compose-X to deploy NGINX simple application
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, nginx

.. _examples_e2e_nginx:

======================
NGINX static content
======================

Local use of docker-compose
============================

As a developer you probably want to be able to quickly iterate on your code and get something started locally quickly.
Docker compose is great to allow you to do just that, and generally there are two ways people do this:

* Generate the code locally and mount it into a docker volume to run
* Build a new image on the fly just before docker-compose starts the new containers

So let's look at our basic docker-compose file.

.. code-block:: yaml
    :caption: docker-compose.yaml

    ---
    # Base NGINX with small page example

    version: "3.8"
    volumes:
      app:

    services:
      frontend:
        image: ${REGISTRY_URI}frontend:${TAG:-latest}
        ports:
          - protocol: tcp
            target: 80
        build:
          context: .
          dockerfile: Dockerfile
        deploy:
          resources:
            limits:
              cpus: 0.5
              memory: 256MB
            reservations:
              cpus: 0.1
              memory: 128MB

We declared an app volume in the top level, that we can choose or not to use. In the docker-compose.yaml file, we choose
not to use it. It will illustrate the override feature of docker-compose.

We however set some settings that instruct docker on the compute resources that we wish to reserve and limit for the container.
We also indicate docker-compose how to build a new image for us. This covers the "build-on-the-fly" aspect.

But what about using files you edited locally that you can just load up (i.e. .jar file, html/css)?
Well, for local development you can create a new file that docker-compose will automatically discover and use: **docker-compose.override.yaml**

Let's have a look at it

.. code-block:: yaml
    :caption: docker-compose.override.yaml

    version: "3.8"
    volumes:
      app: # Using the same volume name, we override the config to mount a local file system
        driver: local
        driver_opts:
          o: bind
          device: ./app
          type: bind

    services:
      frontend:
        image: ${REGISTRY_URI}nginx:${TAG:-latest}
        volumes:
          # We mount our volume app to NGINX default path
          - app:/usr/share/nginx/html:ro
        ports:
          - protocol: tcp
            published: 8080
            target: 80


Here we only change a few settings. First off, we indicate that our app volume, now has more properties and is mounting
a **local** directory that is our **./app**, where in this case, we have put our index.html

We then indicate that we now want to just use the nginx original docker image and simply we mount the **app** volume onto
**/usr/share/nginx/html** which the default root of our NGINX files.

.. note::

    We mount it in read only, but if your application needs to write files into a folder, either remove *:ro* from
    **app:/usr/share/nginx/html:ro** or create a new volume and mount it where your application is expecting to be
    able to write to, for example, as shown below.

    .. code-block::
        :caption: Add a volume and mount it to container

        volumes:
          uploads:
        services:
          frontend:
            volumes:
              - app:/usr/share/nginx/html:ro
              - uploads:/opt/uploads

Okay so let's see what we have got.

.. code-block:: bash

    # That will read the content of docker-compose.yaml and
    # docker-compose.override.yaml to create volumes and containers
    docker-compose up -d
    docker-compose ps
    curl localhost:8080/

Great, our application works, so now let's do some cleanup

.. code-block:: bash

    docker-compose down -v --rmi local
    docker-compose rm

Now, let's build the image that will copy the content of our ./app folder into the docker image so we can ship it anywhere.

.. code-block:: bash

    # Using -f, we indicate that we only want to consider the content of our main docker-compose file
    docker-compose -f docker-compose.yaml build

Now, that build our image locally. But we need it in AWS ECR in order to deploy it.

Build the image and push to docker repository
==============================================

.. note::

    If you intend to use a different docker images store, i.e. quay.io or dockerhub, ensure to have logged in accordingly.

If you have not already, let's create a new ECR Repository, and let's log into it with docker.

.. code-block::

    # Create the new ECR Repository
    aws ecr create-repository --repository-name frontend

    export AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq -r .Account)
    # We define the Registy URI based on the region and account ID
    export REGISTRY_URI=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION:-$AWS_DEFAULT_REGION}.amazonaws.com/

    # We then log in.
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${REGISTRY_URI}

    # We rebuild the image even if there is no change, so that the image gets tagged properly
    docker-compose -f docker-compose.yaml build
    docker-compose -f docker-compose.yaml push

And that's it, our image has been built and pushed into AWS ECR. So what to do now to get it deployed?


Deploy to AWS
===============

In the spirit of override files, we create another file that is going to be used for our AWS Environment.

.. code-block:: yaml
    :caption: aws-compose-x.yaml

    services:
      frontend:
        x-ecr:
          InterpolateWithDigest: true

    # We need DNS information. We indicate which DNS zone to use publicly and which one to use in the VPC.
    # Given that we do not indicate Lookup, the new DNS Zones will be created.

    x-dns:
      PublicZone:
        Name: mydomain.net # Create a new public route53 zone.
      PrivateNamespace:
        Name: cluster.internal # Create a new AWS CloudMap service discovery instance associated with the VPC

    # We create an ALB and send traffic to our frontend. Note that the listener is not encrypted at this point.
    # To use encryption we need n ACM certificate and set the listener protocol to HTTPS

    x-elbv2:
      public-alb:
        Properties:
          Scheme: internet-facing
          Type: application
        Services:
          - name: frontend:frontend
            port: 80
            protocol: HTTP
            healthcheck: 80:HTTP:/:200 # We expect port 80 with HTTP protocol to work and we expect a 200 OK return
        Listeners:
          - Port: 80
            Protocol: HTTP
            Targets:
              - name: frontend:frontend
                access: /

.. tip::

    In the absence of x-vpc, a new one will be created automatically for you to run the application into.
    In the absence of x-cluster, a new ECS Cluster is automatically created to start the containers into.

.. warning::

    If this is the first time using AWS ECS for you, chances are the IAM Service Role for AWS ECS does not exist yet
    in your AWS account and might lead into a deployment failure the first time around.

Install of ECS Compose-X
-------------------------

If you have not already, you can install compose-x in different ways.

To run it with docker, simply run

.. code-block:: bash

    docker run --rm -v ~/.aws:/root/.aws -v $PWD:/tmp public.ecr.aws/compose-x/compose-x:latest

To use it with python, we recommend to use

.. code-block:: bash

    python3 -m venv compose-x
    source compose-x/bin/activate
    pip install pip -U

    # From PIP
    pip install ecs_composex

    # From source
    git clone https://github.com/compose-x/ecs_composex
    cd ecs_composex

    ## With pip
    pip install .

    ## With poetry
    pip install poetry
    poetry install

Deploy!
---------

In the following example, we are going to use **plan** which is going to ask CFN to create a changeset for all the necessary
resources. You could also use **up** that will either create or update a new / existing stack. The stack name is given by the
**-n** argument.

.. code-block:: bash

    # For the following command, we run docker with our own user so that the generated files
    # do not require sudo access to remove.

    # Using docker
    docker run -u $(id -u):$(id -u) -it --rm -v ~/.aws:/tmp/.aws -e HOME=/tmp -v $PWD:/tmp \
    public.ecr.aws/compose-x/compose-x:latest \
    plan -f docker-compose.yaml -f aws-compose-x.yaml -n frontend-app

    # Using compose-x after install
    ecs-compose-x plan -f docker-compose.yaml -f aws-compose-x.yaml -n frontend-app

    # Output should look like when using plan
    # We create a new VPC and ECS Cluster given we did not specify existing ones.
    2021-08-18 09:26:02 [INFO], No x-vpc detected. Creating a new VPC.
    2021-08-18 09:26:02 [INFO], No cluster information provided. Creating a new one

    # Compose-x will "crunch" all the input and let us know of anything of interest or just some info.
    2021-08-18 09:26:02 [INFO], No external rules defined. Skipping.
    2021-08-18 09:26:02 [ERROR], No scaling range was defined for the service and rule HighCpuUsageAndMaxScaledOut requires it. Skipping
    2021-08-18 09:26:02 [ERROR], No scaling range was defined for the service and rule HighRamUsageAndMaxScaledOut requires it. Skipping
    2021-08-18 09:26:02 [INFO], Family frontend - Service frontend
    2021-08-18 09:26:02 [INFO], LB public-alb only has a unique service. LB will be deployed with the service stack.
    2021-08-18 09:26:02 [WARNING], You defined ingress rules for a NLB. This is invalid. Define ingress rules at the service level.
    2021-08-18 09:26:02 [INFO], Added dependency between service family frontend and elbv2
    2021-08-18 09:26:02 [WARNING], No certificates defined for Listener publicalb80
    2021-08-18 09:26:02 [INFO], publicalb80 has no defined DefaultActions and only 1 service. Default all to service.

    # Compose-X connected all the services and resources. Now generates the CFN templates and put the nested stack templates in AWS S3
    2021-08-18 09:26:02 [INFO], vpc.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/vpc.json
    2021-08-18 09:26:03 [INFO], vpc.params.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/vpc.params.json
    2021-08-18 09:26:03 [INFO], vpc.config.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/vpc.config.json
    2021-08-18 09:26:03 [INFO], frontend.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/frontend.json
    2021-08-18 09:26:09 [INFO], frontend.params.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/frontend.params.json
    2021-08-18 09:26:09 [INFO], frontend.config.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/frontend.config.json
    2021-08-18 09:26:10 [INFO], elbv2.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/elbv2.json
    2021-08-18 09:26:10 [INFO], frontend-app.json uploaded successfully to https://s3.amazonaws.com/ecs-composex-373709687836-eu-west-1/2021/08/18/0926/0bb55b/frontend-app.json

    ====================  ==========================================  ========
    LogicalResourceId     ResourceType                                Action
    ====================  ==========================================  ========
    CloudMapVpcNamespace  AWS::ServiceDiscovery::PrivateDnsNamespace  Add
    EcsCluster            AWS::ECS::Cluster                           Add
    Route53PublicZone     AWS::Route53::HostedZone                    Add
    elbv2                 AWS::CloudFormation::Stack                  Add
    frontend              AWS::CloudFormation::Stack                  Add
    vpc                   AWS::CloudFormation::Stack                  Add
    ====================  ==========================================  ========
    Want to apply? [yN]: N # Do you want to deploy ?
    Cleanup ChangeSet ? [yN]: y If not, do you want to cleanup what got created.


.. note::

    Note that **plan** will wait for user-input so you need to run docker in interactive mode with **-it**

Clean Up
---------

To clean things up, you just need to tell AWS CFN to delete the root stack.

.. code-block:: bash

    aws cloudformation delete-stack --stack-name frontend-app
