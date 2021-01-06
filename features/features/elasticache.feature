Feature: ecs_composex.elasticache

  @elasticache
  Scenario Outline: AWS Elasticache Clusters creation
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution

    Examples:
      | file_path                   | override_file                              |
      | use-cases/blog.features.yml | use-cases/elasticache/create_only.yml      |
      | use-cases/blog.features.yml | use-cases/elasticache/subnets_override.yml |
