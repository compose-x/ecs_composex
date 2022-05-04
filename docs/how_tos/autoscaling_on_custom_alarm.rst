
.. meta::
    :description: ECS Compose-X How To
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, kafka, alarm, autoscaling


.. _how_to_autoscaling_on_custom_alarm:

============================================================
Services step scaling from custom alarm
============================================================

Not all autoscaling should be done on CPU or RAM, and more often than not, these metrics are not particularly relevant
to the workload handled by the services.

So let's take a use-case, which allows us to do event driven services deployment that use a custom metric and scales
our service based on that.


The metric itself
====================

Today we are going to use a metric related to Kafka, which is the consumer lag of a given consumer group.
For those not familiar to Kafka, a consumer group name is the identifier that is used by an application to read
messages and keep track of their ``offset``. That ``offset`` value is a "bookmark" that indicates where from the
application should start reading, since the last time it did.

In AWS MSK, you have that metric published for you in the CloudWatch MSK namespace, but here today we are going to consider
that we are publishing that metric. We are going to skip over how the metric is published, but that is something you
can have a look at in `the labs`_

The reason for picking this metric: it is a real use-case that as working on ECS Compose-X, has been implemented using it.

But as other companies do, if you have metrics such as number of sales, concurrent logged in users etc, you could scale
based on those custom metrics.

Configure the service
========================

Let's take our docker-compose file and add the necessary to our service definition to make it ECS and Application Autoscaling aware


.. code-block:: yaml

    services:
      etl-consumer-service:
        deploy:
          replicas: 1
        image: my-etl-application
        x-scaling:
          Range: "0-12"


And that's it, we just need to indicate what range we want the service to scale with. When the service will be created,
it will start a container. That will allow us to

* test that our container runs properly
* configuration is correct

and most importantly, given that we are allowing to go down to 0 (no) container running, it will prove our scaling works
when ECS and Application Autoscaling correct the ``desired_count`` for the service.

Configure the alarm
=========================

Now, we know all the dimensions that we need to look out for. So we configure the alarm in our compose file


.. code-block:: yaml

    x-alarms:
      etl-service-consumer-lag:
        Properties: &kafka_lag_alarm
          AlarmName: etl-service-consumer-lag
          ActionsEnabled: true
          MetricName: kafka_consumergroup_group_topic_sum_lag
          Namespace: ECS/ContainerInsights/Prometheus
          Statistic: Sum
          Dimensions:
            - Name: cluster_name
              Value: kafka-cluster
            - Name: topic
              Value: kafka-topic-name
            - Name: group
              Value: etl-service-consumer-group-name
          Period: 300
          EvaluationPeriods: 1
          DatapointsToAlarm: 1
          Threshold: 1.0
          ComparisonOperator: GreaterThanOrEqualToThreshold
          TreatMissingData: missing
        Services:
          etl-consumer-service:
            Scaling:
              Steps:
                - LowerBound: 0 # From 0 of consumer lag
                  UpperBound: 1000 # To 1000 messages in lag
                  Count: 1
                - LowerBound: 1000 # From 1000 of consumer lag
                  UpperBound: 10000 # To 10000 messages in lag
                  Count: 6
                - LowerBound: 10000 # From 10000 and above
                  Count: 12


Et voilá ! The alarm will be automatically created with your deployment, retrieve the properties it needs from your
ECS Service to scale it appropriately. When the alarm changes state, it updates Application Autoscalilng which in turn
drives the change of ``desired_count`` of our service.



.. _the labs: https://labs.compose-x.io
