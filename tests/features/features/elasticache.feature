Feature: ecs_composex.elasticache

  @elasticache
  Scenario Outline: AWS Elasticache Clusters creation
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution

    Examples:
      | file_path                   | override_file                              |
      | use-cases/blog.features.yml | use-cases/elasticache/create_only.yml      |
      | use-cases/blog.features.yml | use-cases/elasticache/subnets_override.yml |
