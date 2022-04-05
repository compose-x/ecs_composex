#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Custom exceptions for compose-x
"""


class ComposeBaseException(Exception):
    """
    Top class for Compose-X Exceptions
    """

    def __init__(self, msg, *args):
        super().__init__(msg, *args)


class IncompatibleOptions(ComposeBaseException):
    """
    Exception when two x-resources conflict, i.e. when you try to use Lookup on x-cloudmap and create a new VPC
    """
