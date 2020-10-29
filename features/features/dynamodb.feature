Feature: ecs_composex.dynamodb

  @dynamodb
  Scenario Outline: Working dynamodb docker-compose files
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate

    Examples:
      | file_path                   | override_file                         |
      | use-cases/blog.features.yml | use-cases/dynamodb/table_with_gsi.yml |
      | use-cases/blog.features.yml | use-cases/dynamodb/table.yml          |
      | use-cases/blog.features.yml | use-cases/dynamodb/tables.yml         |
      | use-cases/blog.features.yml | use-cases/dynamodb/create_lookup.yml  |
