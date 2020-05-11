import boto3

from behave import given, when, then

EC2 = boto3.client("ec2")


def get_vpc(context):
    """
    Function to define the VPC for context
    """
    context.vpc_filters = [{"Name": "tag:Name", "Values": [context.vpc_name]}]
    vpcs_r = EC2.describe_vpcs(Filters=context.vpc_filters)
    if not vpcs_r["Vpcs"]:
        raise ValueError(f"No VPC named {context.vpc_name} found")
    elif vpcs_r["Vpcs"] and len(vpcs_r["Vpcs"]) != 1:
        raise ValueError(f"More than one VPC with tag:Name {context.vpc_name} found")
    context.vpc = vpcs_r["Vpcs"][0]


def get_app_subnets(context):
    context.app_subnets_filters = [
        {"Name": "tag:vpc::usage", "Values": ["application"]},
        {"Name": "vpc-id", "Values": [context.vpc["VpcId"]]},
    ]
    subnets_r = EC2.describe_subnets(Filters=context.app_subnets_filters)
    if not subnets_r["Subnets"]:
        raise ValueError(
            f"No subnets with tag:vpc::usage application found for vpc {context.vpc['VpcId']}"
        )
    context.subnets = subnets_r["Subnets"]


def get_vpc_nats(context):
    """
    Function to get the VPC Nat Gateways
    """
    context.nat_filters = [
        {"Name": "vpc-id", "Values": [context.vpc["VpcId"]]},
        {"Name": "state", "Values": ["available"]},
    ]
    nats_r = EC2.describe_nat_gateways(Filters=context.nat_filters)
    if not nats_r["NatGateways"]:
        raise ValueError(f"No NAT Gateway found for VPC {context.vpc['VpcId']}")
    context.nat_gws = nats_r["NatGateways"]


def get_route_tables(context):
    """
    Function to define the VPC Route tables
    """
    context.rtbs_filters = [
        {"Name": "tag:Name", "Values": ["AppRtb*"]},
        {"Name": "vpc-id", "Values": [context.vpc["VpcId"]]},
    ]
    rtbs_r = EC2.describe_route_tables(Filters=context.rtbs_filters)
    if not rtbs_r["RouteTables"]:
        raise ValueError(
            f"No route table found with tag Name:AppRtb* for VPC {context.vpc['VpcId']}"
        )
    context.rtbs = rtbs_r["RouteTables"]


@given('I have a VPC called {name}')
def step_impl(context, name):
    context.vpc_name = name
    get_vpc(context)


@when("I want single NAT for AppSubnets")
def step_impl(context):
    get_app_subnets(context)
    get_vpc_nats(context)
    get_route_tables(context)


@then("I should have only one nat gateway for AppSubnets")
def step_impl(context):
    assert len(context.nat_gws) == 1
    for rtb in context.rtbs:
        routes = rtb["Routes"]
        for route in routes:
            if route["DestinationCidrBlock"] == "0.0.0.0/0":
                assert "NatGatewayId" in route.keys()
                assert route["NatGatewayId"] == context.nat_gws[0]["NatGatewayId"]


@then("I should have one route table per subnet")
def step_impl(context):
    assert len(context.nat_gws) == len(context.subnets)


@when(u'I want one NAT per AppSubnet')
def step_impl(context):
    raise NotImplementedError(u'STEP: When I want one NAT per AppSubnet')


@then(u'I should have one NAT per AppSubnet in the same AZ')
def step_impl(context):
    raise NotImplementedError(u'STEP: Then I should have one NAT per AppSubnet in the same AZ')
