#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os import path

import pytest
from ecs_composex.compute.spot_fleet import (
    generate_spot_fleet_template,
    DEFAULT_SPOT_CONFIG,
)
from ecs_composex.compute.hosts_template import add_hosts_resources


@pytest.fixture
def here():
    return path.abspath(path.dirname(__file__))


@pytest.fixture
def spotfleet_input_config():
    """
    Function to set different spot instances configurations
    :return: Spotfleet configuration
    :rtype: dict
    """
    return {
        "use_spot": True,
        "bid_price": 0.21,
        "spot_instance_types": {
            "r5.xlarge": {"weight": 3},
            "r5.2xlarge": {"weight": 7},
            "r5.4xlarge": {"weight": 15},
            "m5a.2xlarge": {"weight": 8},
        },
    }


@pytest.fixture
def eu_azs():
    """
    Fixture to simulate a region azs
    :return: list of azs
    :rtype: list
    """
    azs = ["a", "b", "c"]
    return [f"eu-west-1{letter}" for letter in azs]


@pytest.fixture
def us_azs():
    """
    Fixture to simulate a region azs
    :return: list of azs
    :rtype: list
    """
    azs = ["a", "b", "c", "d", "e", "f"]
    return [f"us-west-1{letter}" for letter in azs]


def test_spotfleet_defaults(eu_azs):
    """
    Testing spotfleet input
    """
    kwargs = {}
    default_configs_len = len(DEFAULT_SPOT_CONFIG["spot_instance_types"].keys())
    expected_overrides = len(eu_azs) * default_configs_len
    template = generate_spot_fleet_template(eu_azs, **kwargs)
    fleet = template.resources["EcsClusterFleet"]
    overrides = (
        fleet.properties["SpotFleetRequestConfigData"]
        .LaunchTemplateConfigs[0]
        .Overrides
    )
    assert len(overrides) == expected_overrides


def test_spotfleet_overrides(eu_azs, spotfleet_input_config):
    """
    Testing spotfleet input
    """
    kwargs = {"spot_config": spotfleet_input_config}
    default_configs_len = len(spotfleet_input_config["spot_instance_types"].keys())
    expected_overrides = len(eu_azs) * default_configs_len
    template = generate_spot_fleet_template(eu_azs, **kwargs)
    fleet = template.resources["EcsClusterFleet"]
    overrides = (
        fleet.properties["SpotFleetRequestConfigData"]
        .LaunchTemplateConfigs[0]
        .Overrides
    )
    assert len(overrides) == expected_overrides


def test_spotfleet_overrides_azs(us_azs, spotfleet_input_config):
    """
    Testing spotfleet input
    """
    kwargs = {"spot_config": spotfleet_input_config}
    default_configs_len = len(spotfleet_input_config["spot_instance_types"].keys())
    expected_overrides = len(us_azs) * default_configs_len
    template = generate_spot_fleet_template(us_azs, **kwargs)
    fleet = template.resources["EcsClusterFleet"]
    overrides = (
        fleet.properties["SpotFleetRequestConfigData"]
        .LaunchTemplateConfigs[0]
        .Overrides
    )
    assert len(overrides) == expected_overrides


def test_hosts_resources(eu_azs):
    """
    Function to test add_hosts_resources
    :param eu_azs:
    """
    template = generate_spot_fleet_template(eu_azs, **{})
    add_hosts_resources(template)
    resources = template.resources
    assert "LaunchTemplate" in resources
    template.to_yaml()
