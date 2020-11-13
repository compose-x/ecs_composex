Feature: ecs_composex.docdb

  @docdb
  Scenario Outline: New s3 buckets and services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution

    Examples:
      | file_path                   | override_file                   |
      | use-cases/blog.features.yml | use-cases/docdb/create_only.yml |
