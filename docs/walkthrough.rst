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
          - 8080
          - 80
        environment:
          description: front-app
        links:
          - serviceB

      serviceB:
        image: link_to_image_b
        ports:
          - 80
          - 8080
        environment:
          description: auth-app
    x-rds:
      db:
        Properties:
          Engine: aurora-mysql
          EngineVersion: 5.7.12
        Settings: {}
        Services:
          - name: serviceB
            access: RW

    x-elbv2:
      public-lb:
        Properties:
          Scheme: public-facing
          Type: application
        Settings:
         http2: True
         cross_zone: True
        MacroParameters:
          Ingress:
            ExtSources:
              - Ipv4: "0.0.0.0/0"
                Description: ANY
              - Ipv4: "1.1.1.1/32"
                Description: CLOUDFLARE
                Name: CLOUDFLARE
        Listeners:
          - Port: 80
            Protocol: HTTP
            DefaultActions:
              - Redirect: HTTP_TO_HTTPS
          - Port: 443
            Protocol: HTTP
            Certificates:
              - x-acm: public-acm-01
              - CertificateArn: arn:aws:acm:eu-west-1:012345678912:certificate/102402a1-d0d2-46ff-b26b-33008f072ee8
            Targets:
              - name: serviceA:serviceA
                access: /
              - name: serviceB:serviceB
                access: /login
        Services:
          - name: serviceA:serviceA
            port: 80
            healthcheck: 8080:HTTP:5:2:15:3:/ping.This.Method:200,201
          - name: serviceB:serviceB
            port: 80
            healthcheck: 8080:HTTP:5:2:15:3:/health
