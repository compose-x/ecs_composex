
.. meta::
    :description: ECS Compose-X to deploy NGINX simple application
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, nginx

.. _examples_e2e_nginx:


docker-compose up -d
curl localhost:8080


docker-compose down
docker-compose rm

Log into AWS ECR

docker-compose build
docker-compose push

Deploy to AWS

ecs-compose-x plan -n test-nginx -f docker-compose.yaml -f aws-compose-x.yaml
