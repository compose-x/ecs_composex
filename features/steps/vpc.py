from troposphere.ec2 import NatGateway
from behave import given, when, then
from ecs_composex.vpc.vpc_template import generate_vpc_template


@given("I want a VPC")
def step_impl(context):
    context.cidr_block = "172.16.0.0/20"
    context.azs = ["eu-west-1a", "eu-west1-b"]


@when("I want single NAT")
def step_impl(context):
    context.single_nat = True


@when("this is for production")
def step_impl(context):
    context.single_nat = False


@then("I should have only one nat gateway")
def step_impl(context):
    template = generate_vpc_template(
        context.cidr_block, context.azs, context.single_nat
    )
    resources = template.resources
    nats = 0
    for resource_name in resources:
        if isinstance(resources[resource_name], NatGateway):
            nats += 1
    assert nats == 1


@then("I should have one nat gateway per az")
def step_impl(context):
    template = generate_vpc_template(
        context.cidr_block, context.azs, context.single_nat
    )
    resources = template.resources
    nats = 0
    for resource_name in resources:
        if isinstance(resources[resource_name], NatGateway):
            nats += 1
    assert nats == 2
