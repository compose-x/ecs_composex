.. highlight:: shell

===================
Example walkthrough
===================

Let's take an existing very simple docker compose file with two services.

.. code-block:: yaml

    services:
      serviceA:
        image: link_to_image_a
        ports:
          - 8080:80
          - 8443:443
        environment:
          description: reverse-proxy
        links:
          - serviceB

      serviceB:
        image: link_to_image_b
        ports:
          - 8081:80
          - 8444:443
        environment:
          description: BackendApp
        links:
          - db

      db:
        image: mysql
        ports:
          - 3306:3306


This will create the services and the DB and link them together. Now as we discussed earlier, we probably want to use RDS
on AWS to host.

So, to do that, we would add a new rds resource to our docker compose file.

.. code-block:: yaml

    services:
      serviceA:
        image: link_to_image_a
        ports:
          - 8080:80
          - 8443:443
        environment:
          description: reverse-proxy
        links:
          - serviceB

      serviceB:
        image: link_to_image_b
        ports:
          - 8081:80
          - 8444:443
        environment:
          description: BackendApp
        links:
          - db

    x-rds:
      db:
        Properties:
          Engine: aurora-mysql
          EngineVersion: 5.7.12
        Settings: {}
        Services:
          - name: serviceB
            access: RW

So at that point, using ECS ComposeX, we will get a new RDS DB created, which will also have a password stored in AWS
Secrets Manager, and ECS ComposeX will make sure that the service Security Group has ingress access to the RDS endpoint,
and the IAM Role for the ECS Execution Role will be granted access to the secret so it can expose it to the microservice.

But now we also have another issue: our reverse proxy service will by default no be made public. So to provide external
access to it (inbound) we could use a load-balancer. We could use an ALB or NLB. AWS ALB here is more appropriate given we
have an HTTP based application. So we need to indicate to ECS ComposeX that it should create an ALB for the service.

.. code-block::

    services:
      serviceA:
        image: link_to_image_a
        ports:
          - 8080:80
          - 8443:443
        environment:
          description: reverse-proxy
        links:
          - serviceB

      serviceB:
        image: link_to_image_b
        ports:
          - 8081:80
          - 8444:443
        environment:
          description: BackendApp
    x-rds:
      db:
        Properties:
          Engine: aurora-mysql
          EngineVersion: 5.7.12
        Settings: {}
        Services:
          - name: serviceB
            access: RW

    x-configs:
      serviceA:
        network:
          lb_type: application
          is_public: True
          ext_sources:
            - ipv4: 0.0.0.0/0
              protocol: tcp
              source_name: all
