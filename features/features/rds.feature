Feature: ecs_composex.rds

  @rds
  Scenario Outline: Simple RDS with services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I render the docker-compose to composex
    Then I should have a RDS DB
    And services have access to it

    Examples:
      | file_path                   | override_file                |
      | use-cases/blog.features.yml | use-cases/rds/rds_basic.yml  |
      | use-cases/blog.features.yml | use-cases/rds/rds_import.yml |
