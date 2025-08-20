.. meta::
    :description: ECS Compose-X - Transform docker-compose files into production-ready AWS infrastructure
    :keywords: AWS, ECS, Fargate, Docker, Containers, Compose, docker-compose, CloudFormation, Infrastructure as Code

============
ECS ComposeX
============

|PYPI_VERSION| |PYPI_LICENSE| |PY_DLS|

|CODE_STYLE| |ISORT| |TDD| |BDD|

|QUALITY|

|BUILD|

**The no-code Infrastructure-as-Code tool that turns your docker-compose files into production-ready AWS deployments**

🎯 What is ECS Compose-X?
=========================

ECS Compose-X transforms your familiar ``docker-compose.yml`` files into complete AWS cloud infrastructures. It's like having a cloud architect that automatically creates all the AWS resources your application needs - ECS clusters, VPCs, load balancers, databases, security groups, IAM roles - all with production-ready security and best practices.

The Problem It Solves
----------------------

* **"It works on my laptop"** - Your docker-compose app runs locally but deploying to AWS is complex
* **Security headaches** - Setting up proper IAM roles, security groups, and networking is error-prone
* **Infrastructure complexity** - Creating CloudFormation templates for every AWS service is time-consuming
* **Maintenance burden** - Keeping infrastructure code in sync with application changes

The Solution
------------

.. code-block:: bash

    # 1. Use your existing docker-compose.yml
    # 2. Add optional AWS extensions
    # 3. Deploy everything to AWS
    ecs-compose-x render -f docker-compose.yml -f aws-settings.yml

🚀 Quick Start (5 minutes)
===========================

Prerequisites
-------------

* AWS CLI configured with appropriate permissions
* Docker installed (for local testing)
* Python 3.9+

1. Install ECS Compose-X
------------------------

.. code-block:: bash

    pip install ecs-composex

    # or use Docker
    docker run public.ecr.aws/compose-x/compose-x:latest

2. Create a simple app
----------------------

.. code-block:: yaml

    # docker-compose.yml
    version: '3.8'
    services:
      web:
        image: nginx:latest
        ports:
          - "80:80"

      api:
        image: my-app:latest
        ports:
          - "5000:5000"
        environment:
          - DATABASE_URL=${DATABASE_URL}

3. Add AWS configuration (optional)
-----------------------------------

.. code-block:: yaml

    # aws-settings.yml
    x-rds:
      my-database:
        Engine: postgres
        EngineVersion: "13"
        DatabaseName: myapp
        MasterUsername: admin

    services:
      api:
        x-rds:
          - my-database  # Automatically configures access

4. Deploy to AWS
----------------

.. code-block:: bash

    ecs-compose-x render \
      -f docker-compose.yml \
      -f aws-settings.yml \
      -n my-app-stack \
      -d ./cloudformation-templates

    aws cloudformation deploy \
      --template-file ./cloudformation-templates/root.yml \
      --stack-name my-app-stack \
      --capabilities CAPABILITY_IAM

**That's it!** Your app is now running on AWS ECS with:

* ✅ Secure VPC with public/private subnets
* ✅ Application Load Balancer with HTTPS
* ✅ ECS Fargate cluster with auto-scaling
* ✅ RDS PostgreSQL database with secure access
* ✅ IAM roles with least-privilege permissions
* ✅ CloudWatch logging and monitoring

🏗️ Architecture Overview
=========================

.. code-block:: text

    Local docker-compose.yml + AWS extensions
                     ↓
            ECS Compose-X (Python)
                     ↓
         CloudFormation Templates
                     ↓
             AWS Infrastructure

    ┌─────────────────────────────────────────────────────────┐
    │                        AWS Cloud                        │
    │  ┌─────────────────────────────────────────────────┐   │
    │  │                    VPC                          │   │
    │  │  ┌─────────────┐    ┌──────────────────────┐   │   │
    │  │  │   Public    │    │     Private          │   │   │
    │  │  │   Subnet    │    │     Subnet           │   │   │
    │  │  │             │    │                      │   │   │
    │  │  │  ┌────────┐ │    │  ┌─────────────────┐ │   │   │
    │  │  │  │  ALB   │ │    │  │   ECS Fargate   │ │   │   │
    │  │  │  │        │ │    │  │   ┌───────────┐ │ │   │   │
    │  │  │  └────────┘ │    │  │   │   Tasks   │ │ │   │   │
    │  │  └─────────────┘    │  │   └───────────┘ │ │   │   │
    │  │                     │  └─────────────────┘ │   │   │
    │  │                     │                      │   │   │
    │  │                     │  ┌─────────────────┐ │   │   │
    │  │                     │  │      RDS        │ │   │   │
    │  │                     │  └─────────────────┘ │   │   │
    │  └─────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────┘

🌟 Key Features
===============

🔒 Security by Default
----------------------

* Automatic IAM roles with least-privilege permissions
* VPC with private subnets for databases
* Security groups with minimal required access
* Secrets management integration

🎛️ 20+ AWS Services Supported
------------------------------

**Compute:** ECS Fargate, EC2, Auto Scaling

**Storage:** S3, EFS volumes

**Databases:** RDS, DynamoDB, DocumentDB, ElastiCache

**Networking:** VPC, ALB/NLB, Route53, CloudFront

**Monitoring:** CloudWatch, X-Ray tracing

**Security:** IAM, KMS, Secrets Manager, ACM

🔄 DevOps Ready
---------------

* GitOps workflow compatible
* Blue/green deployments
* Rollback capabilities
* Multi-environment support
* CI/CD pipeline integration

📈 Production Scale
-------------------

* Auto-scaling based on CPU/memory
* Multi-AZ deployments for high availability
* Load balancing with health checks
* CloudWatch alarms and notifications

📚 Real-World Examples
======================

Microservices with Database
---------------------------

.. code-block:: yaml

    # docker-compose.yml
    version: '3.8'
    services:
      frontend:
        image: my-frontend:latest
        ports:
          - "80:80"

      api:
        image: my-api:latest
        ports:
          - "8080:8080"
        depends_on:
          - database

    # aws-settings.yml
    x-rds:
      database:
        Engine: postgres
        DatabaseName: myapp
        MasterUsername: admin

    x-elbv2:
      main-lb:
        Type: application

    services:
      api:
        x-rds:
          - database
        x-scaling:
          Range: "2-10"

Event-Driven Architecture
-------------------------

.. code-block:: yaml

    x-sqs:
      user-events:
        MessageRetentionPeriod: 1209600  # 14 days

    x-sns:
      notifications:
        DisplayName: "App Notifications"

    services:
      event-processor:
        image: my-processor:latest
        x-sqs:
          - user-events
        x-sns:
          - notifications

More examples: `Interactive Labs`_

🛠️ Advanced Usage
==================

Custom CloudFormation Resources
-------------------------------

.. code-block:: yaml

    x-resources:
      MyCustomResource:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: my-custom-bucket
          PublicReadPolicy: false

Environment-Specific Overrides
------------------------------

.. code-block:: bash

    # Production deployment
    ecs-compose-x render -f docker-compose.yml -f prod-settings.yml

    # Staging deployment
    ecs-compose-x render -f docker-compose.yml -f staging-settings.yml

Integration with CI/CD
-----------------------

.. code-block:: yaml

    # .github/workflows/deploy.yml
    - name: Deploy to AWS
      run: |
        ecs-compose-x render -f docker-compose.yml -f aws-prod.yml -n ${{ env.STACK_NAME }}
        aws cloudformation deploy --template-file ./templates/root.yml --stack-name ${{ env.STACK_NAME }}

What does ECS Compose-X do automatically?
==========================================

* **Networking**: Creates VPC, subnets, security groups, and NAT gateways
* **Load Balancing**: Sets up Application Load Balancers with health checks
* **Service Discovery**: Configures AWS Cloud Map for service-to-service communication
* **Auto Scaling**: Implements CPU/memory-based scaling policies
* **Monitoring**: Sets up CloudWatch logs, metrics, and alarms
* **Security**: Creates least-privilege IAM roles and policies
* **Secrets**: Manages database credentials and API keys securely
* **SSL/TLS**: Provisions and manages SSL certificates
* **Database Access**: Configures secure database connections and credentials injection

Installation Options
====================

Virtual Environment (Recommended)
----------------------------------

.. code-block:: bash

    python3 -m venv venv
    source venv/bin/activate
    pip install pip -U
    pip install ecs-composex

Docker
------

.. code-block:: bash

    # Interactive mode
    docker run --rm -it -v ~/.aws:/root/.aws public.ecr.aws/compose-x/compose-x:latest

    # One-time command
    docker run --rm -v ~/.aws:/root/.aws -v $(pwd):/workspace public.ecr.aws/compose-x/compose-x:latest render -f docker-compose.yml

User Installation
-----------------

.. code-block:: bash

    pip install ecs-composex --user

From Source
-----------

.. code-block:: bash

    git clone https://github.com/compose-x/ecs_composex.git
    cd ecs_composex
    pip install .

CLI Reference
=============

.. code-block:: bash

    # Render CloudFormation templates
    ecs-compose-x render -f docker-compose.yml -n my-stack -d ./output

    # Deploy directly (requires AWS CLI)
    ecs-compose-x up -f docker-compose.yml -n my-stack

    # Create new stack
    ecs-compose-x create -f docker-compose.yml -n my-stack

    # Update existing stack
    ecs-compose-x update -f docker-compose.yml -n my-stack

    # Get all options
    ecs-compose-x --help

Supported docker-compose Features
==================================

ECS Compose-X supports most standard docker-compose features plus AWS-specific extensions:

**Standard Compose:**

* Services, ports, volumes, networks
* Environment variables and secrets
* Depends_on and links
* Deploy resources and scaling
* Health checks and logging

**AWS Extensions:**

* ``x-ecs``: ECS-specific configurations
* ``x-rds``: RDS database definitions
* ``x-elbv2``: Load balancer configurations
* ``x-s3``: S3 bucket definitions
* ``x-sqs``: SQS queue configurations
* ``x-sns``: SNS topic definitions
* ``x-vpc``: VPC and networking settings
* And 15+ more AWS services

See the `Compatibility Matrix`_ for complete details.

Documentation & Resources
=========================

* 📚 `Complete Documentation`_ - Comprehensive guides and API reference
* 🧪 `Labs & Walkthroughs`_ - Interactive examples and tutorials
* 📝 `Blog`_ - Tutorials and best practices
* 🐛 `Report Issues`_ - Bug reports and feature requests
* 🎯 `Feature Requests`_ - Request new AWS service integrations

Community & Support
====================

ECS Compose-X is actively maintained and has a growing community:

* **Discord/Slack**: Real-time community support
* **GitHub Discussions**: Design discussions and Q&A
* **Blog**: Regular tutorials and best practices
* **Labs**: Interactive examples and tutorials
* **Priority Support**: Feature requests from community members get prioritized

Contributing
============

We love contributions! Whether it's:

* 🐛 Bug reports and fixes
* ✨ New AWS service integrations
* 📖 Documentation improvements
* 💡 Ideas and suggestions
* 🧪 Example applications

See our `Contributing Guide`_ to get started.

Why Choose ECS Compose-X?
=========================

**vs. AWS CDK**
  - Uses familiar docker-compose syntax instead of programming languages
  - No need to learn TypeScript/Python CDK constructs
  - Automatic best practices and security

**vs. Terraform**
  - Docker-compose native, no translation needed
  - Built-in AWS service integrations
  - Automatic IAM and networking configuration

**vs. AWS Copilot**
  - More AWS services supported (20+ vs 5)
  - Existing docker-compose file compatibility
  - Advanced networking and database features

**vs. Manual CloudFormation**
  - Dramatically less code to write and maintain
  - Automatic security and networking best practices
  - Service discovery and scaling built-in

License
=======

ECS Compose-X is licensed under the `Mozilla Public License 2.0`_.

---

**Ready to deploy your docker-compose apps to AWS?**

Get started: `Installation Guide`_

*Made with ❤️ by the Compose-X community*


.. _`Documentation`: https://docs.compose-x.io
.. _`Complete Documentation`: https://docs.compose-x.io
.. _`Interactive Labs`: https://labs.compose-x.io/
.. _`Labs`: https://labs.compose-x.io/
.. _`Blog`: https://blog.compose-x.io/
.. _`Feature Requests`: https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=enhancement&template=feature_request.md&title=%5BFR%5D
.. _`Report Issues`: https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=bug&template=bug_report.md&title=%5BBUG%5D
.. _`Community Discussions`: https://github.com/compose-x/ecs_composex/discussions
.. _`Compatibility Matrix`: https://docs.compose-x.io/compatibility/docker_compose.html
.. _`Contributing Guide`: https://github.com/compose-x/ecs_composex/blob/main/CONTRIBUTING.rst
.. _`Mozilla Public License 2.0`: https://github.com/compose-x/ecs_composex/blob/master/LICENSE
.. _`Installation Guide`: https://docs.compose-x.io/installation.html

.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiWjIrbSsvdC9jZzVDZ3N5dVNiMlJCOUZ4M0FQNFZQeXRtVmtQbWIybUZ1ZmV4NVJEdG9yZURXMk5SVVFYUjEwYXpxUWV1Y0ZaOEcwWS80M0pBSkVYQjg0PSIsIml2UGFyYW1ldGVyU3BlYyI6Ik1rT0NaR05yZHpTMklCT0MiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main

.. |PYPI_VERSION| image:: https://img.shields.io/pypi/v/ecs_composex.svg
        :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_DL| image:: https://img.shields.io/pypi/dm/ecs_composex
    :alt: PyPI - Downloads
    :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_LICENSE| image:: https://img.shields.io/pypi/l/ecs_composex
    :alt: PyPI - License
    :target: https://github.com/compose-x/ecs_composex/blob/master/LICENSE

.. |PYPI_PYVERS| image:: https://img.shields.io/pypi/pyversions/ecs_composex
    :alt: PyPI - Python Version
    :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_WHEEL| image:: https://img.shields.io/pypi/wheel/ecs_composex
    :alt: PyPI - Wheel
    :target: https://pypi.python.org/pypi/ecs_composex

.. |CODE_STYLE| image:: https://img.shields.io/badge/codestyle-black-black
    :alt: CodeStyle
    :target: https://pypi.org/project/black/

.. |TDD| image:: https://img.shields.io/badge/tdd-pytest-black
    :alt: TDD with pytest
    :target: https://docs.pytest.org/en/latest/contents.html

.. |BDD| image:: https://img.shields.io/badge/bdd-behave-black
    :alt: BDD with Behave
    :target: https://behave.readthed.io/en/latest/

.. |QUALITY| image:: https://sonarcloud.io/api/project_badges/measure?project=compose-x_ecs_composex&metric=alert_status
    :alt: Code scan with SonarCloud
    :target: https://sonarcloud.io/dashboard?id=compose-x_ecs_composex

.. |PY_DLS| image:: https://img.shields.io/pypi/dm/ecs-composex
    :target: https://pypi.org/project/ecs-composex/

.. |ISORT| image:: https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336
    :target: https://pycqa.github.io/isort/
