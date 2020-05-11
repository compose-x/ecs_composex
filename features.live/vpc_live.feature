Feature: vpc-live
  @live
  @fixture.vpc.appsubnets
  Scenario Outline: VPC with single NAT
    Given I have a VPC called <name>
    When I want single NAT for AppSubnets
    Then I should have only one nat gateway for AppSubnets

    Examples: VPC name
    | name |
    | case01|

  @live
  Scenario Outline: VPC With multiple NAT
    Given I have a VPC called <name>
    When I want one NAT per AppSubnet
    Then I should have one NAT per AppSubnet in the same AZ

    Examples: VPC Name
    |name|
    |case02|
