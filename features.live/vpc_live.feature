Feature: vpc-live
  @live
  Scenario Outline: VPC with single NAT
    Given I have a VPC called <name>
    When I want single NAT for AppSubnets
    Then I should have only one nat gateway for AppSubnets

    Examples: VPC name
    | name |
    | standalone-vpc|
