Feature: ecs_composex.rds

  @rds
  Scenario Outline: Simple RDS with services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I render the docker-compose to composex
    Then I render all files to verify execution

    Examples:
      | file_path                   | override_file                                 |
      | use-cases/blog.features.yml | use-cases/rds/rds_basic.yml                   |
      | use-cases/blog.features.yml | use-cases/rds/subnets_override.yml            |
      | use-cases/blog.features.yml | use-cases/rds/rds_cluster_multi_instances.yml |
      | use-cases/blog.features.yml | use-cases/rds/rds_with_iam_access.yml         |

  @rds @lookup
  Scenario Outline: Simple RDS with services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I render the docker-compose to composex
    Then services have access to it

    Examples:
      | file_path                   | override_file                |
      | use-cases/blog.features.yml | use-cases/rds/rds_import.yml |
