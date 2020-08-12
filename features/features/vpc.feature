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

  Scenario Outline: No mesh created with the services
    Given I use <file_path> as my docker-compose file
    Then  I render the docker-compose to composex to validate
    Examples:
    |file_path|
    |use-cases/blog-with-vpc-use.yml|
