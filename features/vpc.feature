Feature: VPC
  Scenario: VPC standalone single AZ
    Given I want a VPC
    And I want single NAT
    Then I should have only one nat gateway

  Scenario: VPC standalone all AZs
    Given I want a VPC
    And this is for production
    Then I should have one nat gateway per az
