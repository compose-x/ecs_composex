.. meta::
    :description: ECS Compose-X advanced network syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, networking, subnets, vpc, cloudmap

.. _x_configs_network_syntax:

======================
services.x-prometheus
======================

.. contents::

`JSON Schema Definition <https://ecs-composex-specs.compose-x.io/schemas_docs/services/x_prometheus.html>`_

This section allows to define some settings to make ECS integration to Prometheus easy.

At the moment, the integration focuses primarily in integration with ECS Insights integration and future version will
add support for AWS AMP and other Prometheus clusters.

Syntax
=======

.. code-block:: yaml

    services:
      serviceA:
        x-prometheus:
          ContainersInsights: ContainersInsights

ContainersInsights
--------------------

.. code-block:: yaml

    EnableTasksDiscovery: bool
    CollectForAppMesh: bool
    CollectForJavaJmx: bool
    CustomRules: [Rule]

.. note::

    Although *CollectForNginx* and *CollectForNginxPlus* are available in the syntax, they have not been tested yet
    and therefore are disabled.

EnableTasksDiscovery
-----------------------

Enables Prometheus ECS Scrapper to monitor ECS Tasks in the definition

CollectForAppMesh
-------------------

Automatically enables and configure the scraping configuration for the envoy sidecar metrics collection.

CollectForJavaJmx
----------------------

This allow to configure automatically the scraping configuration for the JMX endpoint.
This rule relies on the docker label **Java_EMF_Metrics** to be set to **True** so that the scraping configuration
knows which container to attempt to collect the metrics from.

To indicate to the scraper which port to use, define the docker label **ECS_PROMETHEUS_EXPORTER_PORT**

You also have to expose the JMX Port on the container for the ECS Agent container to collect the metrics from it.

Rule
-----

.. code-block:: yaml

    - source_labels:
        - container_name
      label_matcher: str
      dimensions:
        - - ClusterName
          - TaskDefinitionFamily
      metric_selectors:
        - "^startsEnds$"

Examples
=========

.. code-block:: yaml
    :caption: Simple application with JVM Enabled and using ECS Insights with prometheus scraper

    services:
      app03:
        ports:
          - 80:80 # App port
          - target: 9000 # JMX Port
        labels:
          Java_EMF_Metrics: "true"
          ECS_PROMETHEUS_EXPORTER_PORT: 9000
        environment:
          JAVA_OPTS: -javaagent:/opt/jmx_exporter.jar=9000:/opt/prometheus_jmx_config.yaml ${JAVA_OPTS}
        x-prometheus:
          ContainersInsights:
            CollectForAppMesh: false
            CollectForJavaJmx: true
