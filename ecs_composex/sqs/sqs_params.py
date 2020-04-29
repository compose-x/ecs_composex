# -*- coding: utf-8 -*-
""" Parameters for SQS"""

from os import path
from troposphere import Parameter

SQS_ARN_T = "Arn"
SQS_ARN = Parameter(SQS_ARN_T, Type="String")

SQS_NAME_T = "QueueName"
SQS_NAME = Parameter(SQS_NAME_T, Type="String")

DLQ_NAME_T = "DeadLetterQueueName"
DLQ_NAME = Parameter(DLQ_NAME_T, Type="String")

DLQ_ARN_T = "DeadLetterQueueArn"
DLQ_ARN = Parameter(DLQ_ARN_T, Type="String")

RES_KEY = f"x-{path.basename(path.dirname(path.abspath(__file__)))}"
SQS_SSM_PREFIX = f"/{RES_KEY}/"
