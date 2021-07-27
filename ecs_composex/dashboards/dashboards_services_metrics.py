#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

from troposphere import AWS_REGION, AWSHelperFn


class ServiceEcsWidget(object):
    """
    Class to manage a new ECS Service widget
    """

    def __init__(self, service_name, service_param, cluster_param, y_index=0):
        """

        :param str service_name:
        :param troposhere.AWSHelperFn service_param:
        :param troposhere.AWSHelperFn cluster_param:
        """
        self.height = 1 + 6 + 6
        self.widgets = [
            {
                "height": 1,
                "width": 24,
                "y": y_index,
                "x": 0,
                "type": "text",
                "properties": {"markdown": f"# Service {service_name}\n"},
            },
            {
                "height": 6,
                "width": 6,
                "y": 1,
                "x": 0,
                "type": "metric",
                "properties": {
                    "view": "pie",
                    "stacked": False,
                    "metrics": [
                        [
                            "ECS/ContainerInsights",
                            "CpuReserved",
                            "ServiceName",
                            f"${{{service_param.title}}}",
                            "ClusterName",
                            f"${{{cluster_param.title}}}",
                        ],
                        [".", "CpuUtilized", ".", ".", ".", "."],
                    ],
                    "region": f"${{{AWS_REGION}}}",
                    "labels": {"visible": True},
                    "legend": {"position": "hidden"},
                },
            },
            {
                "height": 6,
                "width": 6,
                "y": y_index + 1,
                "x": 6,
                "type": "metric",
                "properties": {
                    "view": "pie",
                    "metrics": [
                        [
                            "ECS/ContainerInsights",
                            "MemoryReserved",
                            "ServiceName",
                            f"${{{service_param.title}}}",
                            "ClusterName",
                            f"${{{cluster_param.title}}}",
                        ],
                        [".", "MemoryUtilized", ".", ".", ".", "."],
                    ],
                    "region": f"${{{AWS_REGION}}}",
                    "labels": {"visible": True},
                    "liveData": False,
                },
            },
            {
                "height": 6,
                "width": 12,
                "y": y_index + 1,
                "x": 12,
                "type": "metric",
                "properties": {
                    "view": "singleValue",
                    "stacked": False,
                    "metrics": [
                        [
                            "ECS/ContainerInsights",
                            "RunningTaskCount",
                            "ServiceName",
                            f"${{{service_param.title}}}",
                            "ClusterName",
                            f"${{{cluster_param.title}}}",
                        ],
                        [".", "PendingTaskCount", ".", ".", ".", "."],
                        [".", "DesiredTaskCount", ".", ".", ".", "."],
                    ],
                    "region": f"${{{AWS_REGION}}}",
                    "legend": {"position": "bottom"},
                    "period": 300,
                    "liveData": False,
                    "singleValueFullPrecision": False,
                },
            },
            {
                "height": 6,
                "width": 12,
                "y": y_index + 7,
                "x": 0,
                "type": "metric",
                "properties": {
                    "view": "timeSeries",
                    "stacked": False,
                    "metrics": [
                        [
                            "AWS/ECS",
                            "MemoryUtilization",
                            "ServiceName",
                            f"${{{service_param.title}}}",
                            "ClusterName",
                            f"${{{cluster_param.title}}}",
                        ],
                        [".", "CPUUtilization", ".", ".", ".", "."],
                    ],
                    "region": f"${{{AWS_REGION}}}",
                    "period": 300,
                    "setPeriodToTimeRange": True,
                    "labels": {"visible": True},
                },
            },
            {
                "height": 6,
                "width": 12,
                "y": y_index + 7,
                "x": 12,
                "type": "metric",
                "properties": {
                    "view": "timeSeries",
                    "stacked": False,
                    "metrics": [
                        [
                            "ECS/ContainerInsights",
                            "NetworkTxBytes",
                            "ServiceName",
                            f"${{{service_param.title}}}",
                            "ClusterName",
                            f"${{{cluster_param.title}}}",
                        ],
                        [".", "NetworkRxBytes", ".", ".", ".", "."],
                    ],
                    "region": f"${{{AWS_REGION}}}",
                    "title": "Network IN/OUT",
                },
            },
        ]
