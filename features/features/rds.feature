Feature: ecs_composex.rds
  @static @rds
  Scenario Outline: Simple RDS with services
    Given I use <file_path> as my docker-compose file
    And I render the docker-compose to composex
    Then I should have a RDS DB
    And services have access to it

    Examples:
    |file_path|
    |use-cases/rds/rds_basic.yml|

#  @static @negative-testing
#  Scenario Outline: Wrong engine version
#    Given I use <file_path> as my docker-compose file
#    Then I should get error raised
#
#    Examples:
#    |file_path|
#    |use-cases/rds/negative-testing/wrong_engine.yml|
