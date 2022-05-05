#!/usr/bin/env python

#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Script to upgrade the docker-compose file with resource definitions to the 0.18 format from previous versions.
It will

* replace x-dns with x-route53 and x-cloudmap for PublicZone and PrivateNamespace respectively
* update the Services [] to the Services {} structure, where applicable.

Once modified, it will render the YAML file wih the loader, which might re-arrange the order of the objects
compared to the original order, but nothing else.

"""

from copy import deepcopy

import yaml
from yaml.loader import Loader

try:
    from compose_x_common.compose_x_common import keyisset, keypresent
except ImportError:
    keyisset = lambda x, y: isinstance(y, dict) and x in y and y[x]
    keypresent = lambda x, y: isinstance(y, dict) and x in y


class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def replace_dns(input_file):
    cloudmap_config = {}
    route_53_config = {}

    with open(input_file) as fd:
        content = yaml.load(fd.read(), Loader=Loader)

    if "x-dns" not in content:
        return
    dns_config = content["x-dns"]
    if keyisset("PrivateNamespace", dns_config):
        cloudmap_config["x-cloudmap"] = {
            "PrivateNamespace": dns_config["PrivateNamespace"]
        }
        content.update(cloudmap_config)
    if keyisset("PublicZone", dns_config):
        route_53_config["x-route53"] = {"PublicZone": dns_config["PublicZone"]}
        content.update(route_53_config)

    del content["x-dns"]

    with open(input_file, "w") as fd:
        fd.write(yaml.dump(content))


def remove_env_settings(resource_definition):
    if keyisset("Settings", resource_definition) and keyisset(
        "EnvNames", resource_definition["Settings"]
    ):
        del resource_definition["Settings"]["EnvNames"]
    if keypresent("Settings", resource_definition) and not keyisset(
        "Settings", resource_definition
    ):
        del resource_definition["Settings"]


def rework_sns_topics(sns_definition):
    if not keyisset("Topics", sns_definition):
        return
    topics = deepcopy(sns_definition["Topics"])
    del sns_definition["Topics"]
    sns_definition.update(topics)


def update_networking(service_name, service_def):
    if not keyisset("x-network", service_def):
        return
    x_network = service_def["x-network"]
    if keypresent("UseCloudmap", x_network):
        del x_network["UseCloudmap"]
    if keypresent("IsPublic", x_network):
        del x_network["IsPublic"]


def update_services(input_file):
    with open(input_file) as fd:
        content = yaml.load(fd.read(), Loader=Loader)
    if not keyisset("services", content):
        return
    services = content["services"]
    for service_name, service_def in services.items():
        update_networking(service_name, service_def)
    with open(input_file, "w") as input_fd:
        input_fd.write(yaml.dump(content, Dumper=MyDumper))


def update_cluster(cluster_def, content):
    if (
        keyisset("x-vpc", content)
        and keyisset("Lookup", content["x-vpc"])
        and keyisset("RoleArn", content["x-vpc"]["Lookup"])
    ):
        role_arn = content["x-vpc"]["Lookup"]["RoleArn"]
    else:
        print("Not found a RoleArn in x-vpc.Lookup or no x-vpc")
        role_arn = None
    if keyisset("Use", cluster_def):
        cluster_name = cluster_def["Use"]
        del cluster_def["Use"]
        new_def = {"Lookup": {"ClusterName": cluster_name}}
        if role_arn:
            new_def["Lookup"]["RoleArn"] = role_arn
        cluster_def.update(new_def)


def reformat_resources_services(input_file):
    db_services = ["x-elasticache", "x-rds", "x-docdb", "x-neptune"]
    excluded = ["x-elbv2"]
    with open(input_file) as fd:
        content = yaml.load(fd.read(), Loader=Loader)
    if not isinstance(content, dict):
        print(input_file, content)
        return
    for key, value in content.items():
        if not key.startswith("x-") or key in excluded:
            continue
        if not isinstance(value, dict):
            continue
        if key == "x-cluster":
            update_cluster(content["x-cluster"], content)
        if key == "x-sns":
            rework_sns_topics(value)
        for res, definition in value.items():
            remove_env_settings(definition)
            if not keyisset("Services", definition) or (
                keyisset("Services", definition)
                and not isinstance(definition["Services"], list)
            ):
                continue
            services = definition["Services"]
            new_services = {}
            for service in services:
                new_service_def = deepcopy(service)
                if not keyisset("name", service) and key in ["x-appmesh"]:
                    continue
                if not keyisset("name", service) and key not in ["x-appmesh"]:
                    raise KeyError(
                        input_file, value, service, "No name set for service"
                    )
                new_services[service["name"]] = new_service_def
                if keyisset("access", service):
                    new_service_def["Access"] = (
                        service["access"]
                        if key not in db_services
                        else {"DBCluster": "RO"}
                    )
                elif not keyisset("access", service) and key in ["x-elbv2", "x-events"]:
                    pass
                else:
                    print(f"{input_file} - no access defined on", key, res, service)
                    exit(1)
                if keyisset("name", new_service_def):
                    del new_service_def["name"]
                if keyisset("access", new_service_def):
                    del new_service_def["access"]
                new_services[service["name"]] = new_service_def
            definition["Services"] = new_services
            print(key, res, "Services", definition["Services"])

    with open(input_file, "w") as input_fd:
        input_fd.write(yaml.dump(content, Dumper=MyDumper))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", dest="input_file", required=True)
    args = parser.parse_args()
    replace_dns(args.input_file)
    reformat_resources_services(args.input_file)
    update_services(args.input_file)
