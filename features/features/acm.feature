Feature: ecs_composex.acm
  @acm
  Scenario Outline: Mesh created with the services
    Given I use <file_path> as my docker-compose file
    And I render the docker-compose to composex
    Then I should have an ACM root stack

    Examples:
    |file_path|
    |use-cases/acm/working_acm.yml|
