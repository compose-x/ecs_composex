#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `ecs_composex` package."""

from troposphere import Template, Parameter

from ecs_composex.common import (
    init_template,
    build_template,
    add_parameters
)
from ecs_composex.vpc import vpc_params


def test_init_template():
    """
    Test that makes sure we get a new template
    """
    tpl = init_template()
    assert isinstance(tpl, Template)
    tpl = init_template('Override')
    assert tpl.description == 'Override'
    add_parameters(tpl, [Parameter('Test', Type='String')])
    assert len(tpl.parameters) == 1
    assert tpl.parameters['Test'].Type == 'String'
    add_parameters(tpl, [vpc_params.VPC_ID])
    assert len(tpl.parameters) == 2
    assert tpl.parameters[vpc_params.VPC_ID_T].Type == vpc_params.VPC_TYPE


def test_build_template():
    """
    Testing build template which is a merge of init and add_parameters
    """
    tpl = build_template(
        'Override',
        [
            vpc_params.VPC_ID,
            vpc_params.VPC_MAP_ID
        ]
    )
    assert isinstance(tpl, Template)
    assert isinstance(tpl.parameters[vpc_params.VPC_ID_T], Parameter)
    assert len(tpl.parameters) == 5
    assert tpl.description == 'Override'


# @pytest.fixture
# def response():
#     """Sample pytest fixture.

#     See more at: http://doc.pytest.org/en/latest/fixture.html
#     """
#     # import requests
#     # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


# def test_content(response):
#     """Sample pytest test function with the pytest fixture as an argument."""
#     # from bs4 import BeautifulSoup
#     # assert 'GitHub' in BeautifulSoup(response.content).title.string
