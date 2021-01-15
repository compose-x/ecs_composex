Feature: ecs_composex.vpc

  @vpc
  Scenario Outline: Various VPC settings
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution
    Examples:
      | file_path                   | override_file                       |
      | use-cases/blog.features.yml | use-cases/vpc/use_existing.yml      |
      | use-cases/blog.features.yml | use-cases/vpc/new_vpc.yml           |
      | use-cases/blog.features.yml | use-cases/vpc/new_with_flowlogs.yml |
