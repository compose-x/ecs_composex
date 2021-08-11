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
===================

.. code-block:: yaml

    EnableCWAgentDebug: bool
    CollectForAppMesh: bool
    CollectForJavaJmx: bool|ExporterConfig
    CollectForNginx: bool|ExporterConfig
    AutoAddNginxPrometheusExporter: bool
    CustomRules: [Rule]

CollectForAppMesh
-------------------

Automatically enables and configure the scraping configuration for the envoy sidecar metrics collection.
The discovery relies on the container for envoy to be named **envoy**. When using x-appmesh, the envoy container
is added automatically and uses the right name.

CollectForJavaJmx
----------------------

Default values
++++++++++++++++

This allow to configure automatically the scraping configuration for the JMX endpoint.

When setting the value to true (boolean) then the following default properties are applied

+------------------------------+-----------+
| JMX Prometheus Exporter Port | 9404      |
+------------------------------+-----------+
| Container label matcher      | ^.*jmx.*$ |
+------------------------------+-----------+
| Container labes              | job       |
+------------------------------+-----------+


CollectForNginx
------------------

When set to true, the following default values are used

+------------------------------+-------------+
| JMX Prometheus Exporter Port | 9113        |
+------------------------------+-------------+
| Container label matcher      | ^.*nginx.*$ |
+------------------------------+-------------+
| Container labes              | job         |
+------------------------------+-------------+

ExporterConfig
------------------

This property allows you to override the source_labels and label matcher for the discovery rule.
This is useful if you have a container that performs the exporting job but is not using the default values

.. code-block:: yaml

    ExporterPort: int
    ExporterPath: str
    source_labels: [str]
    label_matcher: str

ExporterPort
++++++++++++++

The port to use for scraping jobs. Default depends on the type of export

ExporterPath
++++++++++++++

The path at which perform the scraping. Default is **/metrics**

.. hint::

    The source_labels and label_matcher are the same as ones defined in Custom Rules

source_labels
++++++++++++++

List of the docker labels to use to match container that are running an exporter against.
Defaults to **[job]**

label_matcher
++++++++++++++

Regular expression that allows to identify the containers in a task that are exporting. The regular expression is matched
against the values defined in `source_labels`_


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
    :caption: Simple NGINX service with nginx-prometheus-exporter side car auto-added to the task definition.

    services:
      nginx:
        image: ${REGISTRY_URI}sc-ce-kafdrop-nginx:${IMAGE_TAG:-latest}
        volumes:
        - nginx:/etc/nginx/ssl:ro
        networks:
          - internal
        build:
          context: nginx
        deploy:
          labels:
            ecs.task.family: kafdrop
          replicas: 1
          resources:
            reservations:
              cpus: 0.2
              memory: 128M
        ports:
        - 443:443
        depends_on:
          - files-composer
        x-ecr:
          InterpolateWithDigest: true
        x-prometheus:
          ContainersInsights:
            CollectForNginx:
              ExporterPort: 9113
            AutoAddNginxPrometheusExporter: true

.. code-block:: yaml
    :caption: JAVA Application with the jmx exporter configured to export on arbitrary port 1234

    services:
      kafdrop:
        image: public.ecr.aws/compose-x/amazoncorretto:11
        ports:
        - 9000:9000
        - target: 1234
          protocol: tcp
        x-prometheus:
          ContainersInsights:
            EnableCWAgentDebug: true
            CollectForJavaJmx:
              ExporterPort: 1234
        labels:
          job: jmx_prometheus_export
          jmx_prometheus_export: "true"
        environment:
          JMX_PORT: 8888
        volumes:
        - kafdrop:/app:ro
        depends_on:
          - nginx
        deploy:
          labels:
            ecs.task.family: kafdrop
          replicas: 1
          resources:
            reservations:
              cpus: 0.5
              memory: 1GB
        x-iam:
          PermissionsBoundary: ccoe/js-developer
        command: ["/bin/bash", "/app/start.sh"]
        networks:
          - internal

.. seealso::

    `Full Kafdrop configuration walkthrough`_

.. _Full Kafdrop configuration walkthrough: https://labs.compose-x.io/kafka/kafdrop.html
