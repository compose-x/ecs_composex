# -*- coding: utf-8 -*-
""" Parameters for SQS"""

from troposphere import Parameter

SQS_ARN_T = 'SqsQueueArn'
SQS_ARN = Parameter(SQS_ARN_T, Type='String')


SQS_NAME_T = 'QueueName'
SQS_NAME = Parameter(SQS_NAME_T, Type='String')

DLQ_NAME_T = 'DeadLetterQueueName'
DLQ_NAME = Parameter(DLQ_NAME_T, Type='String')
