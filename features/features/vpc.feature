Feature: ecs_composex.vpc
  @vpc
  Scenario: VPC standalone single AZ
    Given I want a VPC
    When I want single NAT
    Then I should have only one nat gateway
  @vpc
  Scenario: VPC standalone all AZs
    Given I want a VPC
    When this is for production
    Then I should have one nat gateway per az
