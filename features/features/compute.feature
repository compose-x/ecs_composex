Feature: ecs_composex.appmesh
  @static @compute

  Scenario Outline: No mesh created with the services
    Given I use <file_path> as my docker-compose file
    And I want to use spot fleet
    Then  I render the docker compose to composex to validate
    Examples:
    |file_path|
    |use-cases/blog-all-features-with-compute.yml|

  @static @compute @iam

  Scenario Outline: No mesh created with the services
    Given I use <file_path> as my docker-compose file
    And I want to use aws profile <profile_name>
    And I want to use spot fleet
    And I render the docker compose to composex
    Then I render all files to verify execution
    Examples:
    |file_path|profile_name|
    |use-cases/blog.yml|lambda|
    |use-cases/blog-all-features.yml|lambda|
    |use-cases/blog-all-features-with-compute.yml|preston|
