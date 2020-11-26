Feature: ecs_composex.vpc

  @vpc
  Scenario: VPC standalone single AZ
    Given I want a VPC
    When I want single NAT
    Then I should have only one nat gateway

  Scenario: VPC standalone all AZs
    Given I want a VPC
    When this is for production
    Then I should have one nat gateway per az

  @vpc @extra-subnets
  Scenario Outline: Extra subnets definition
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    Examples:
      | file_path                   | override_file                  |
      | use-cases/blog.features.yml | use-cases/vpc/use_existing.yml |
