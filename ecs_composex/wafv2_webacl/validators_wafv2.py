#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""Override validator"""


def validate_statement(statement):
    """
    Validate Transformation Type for WebACL TextTransformation
    Property: RuleGroupRule.Statement
    Property: WebACLRule.Statement
    Property: ManagedRuleGroupStatement.ScopeDownStatement
    Property: NotStatement.Statement
    Property: RateBasedStatement.ScopeDownStatement
    """

    from troposphere import AWSHelperFn
    from troposphere.wafv2 import Statement

    if not isinstance(statement, (Statement, AWSHelperFn)):
        raise TypeError(f"{statement} is not a valid Statement", Statement)

    return statement
