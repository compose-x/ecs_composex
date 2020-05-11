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


def get_public_subnets(context):
    context.app_subnets_filters = [
        {"Name": "tag:vpc::usage", "Values": ["public"]},
        {"Name": "vpc-id", "Values": [context.vpc["VpcId"]]},
    ]
    subnets_r = EC2.describe_subnets(Filters=context.app_subnets_filters)
    if not subnets_r["Subnets"]:
        raise ValueError(
            f"No subnets with tag:vpc::usage public found for vpc {context.vpc['VpcId']}"
        )
    context.pub_subnets = subnets_r["Subnets"]


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


def find_nat_subnet_az(context, subnet_id):
    """
    Function to get which AZ the nat is into as per its public subnet
    :return:
    """
    for subnet in context.pub_subnets:
        if subnet["SubnetId"] == subnet_id:
            return subnet


def find_app_subnet_in_az(context, az):
    """
    Function to get the app subnet of the same AZ as the NAT GW
    """
    subnets = []
    for app_subnet in context.subnets:
        if app_subnet["AvailabilityZone"] == az:
            subnets.append(app_subnet)
    if not subnets:
        raise ValueError(f"No application subnet found in AZ {az}")
    return subnets[-1]


def find_app_route_table(context, subnet, nat_gw):
    """
    Function to check that a subnet has only one route table and that route table uses the NAT for ANY dest.
    :param context:
    :param subnet:
    :return:
    """
    for rtb in context.rtbs:
        for assoc in rtb["Associations"]:
            if assoc["SubnetId"] == subnet["SubnetId"]:
                for route in rtb["Routes"]:
                    if "NatGatewayId" in route.keys() and route["NatGatewayId"] == nat_gw["NatGatewayId"]:
                        assert route["DestinationCidrBlock"] == "0.0.0.0/0"
                        return True
    return False


@when(u'I want one NAT per AZ')
def step_impl(context):
    import json
    get_route_tables(context)
    get_app_subnets(context)
    get_vpc_nats(context)
    get_public_subnets(context)
    print(json.dumps(context.rtbs, indent=4))

    # raise NotImplementedError(u'STEP: When I want one NAT per AppSubnet')


@then(u'I should have one NAT per AZ mapping to AppSubnet')
def step_impl(context):
    for nat in context.nat_gws:
        nat_subnet = find_nat_subnet_az(context, nat["SubnetId"])
        nat_az = nat_subnet["AvailabilityZone"]
        app_subnet = find_app_subnet_in_az(context, nat_az)
        assert find_app_route_table(context, app_subnet, nat)
