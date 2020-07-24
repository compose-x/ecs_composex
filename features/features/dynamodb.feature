Feature: ecs_composex.dynamodb
  @dynamodb
  Scenario Outline: Working dynamodb docker-compose files
    Given I use <file_path> as my docker-compose file
    Then I render the docker-compose to composex to validate

    Examples:
    |file_path|
    |use-cases/dynamodb/table.yml|
    |use-cases/dynamodb/table_with_gsi.yml|
