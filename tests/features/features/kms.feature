Feature: ecs_composex.kms

  @kms
  Scenario Outline: Create services with a queue
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution
    Examples:
      | file_path                   | override_file                       |
      | use-cases/blog.features.yml | use-cases/kms/simple_kms.yml        |
      | use-cases/blog.features.yml | use-cases/kms/create_and_lookup.yml |
