Feature: ecs_composex.s3

  @s3
  Scenario Outline: New s3 buckets and services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate

    Examples:
      | file_path          | override_file                     |
      | use-cases/blog.yml | use-cases/s3/simple_s3_bucket.yml |

  Scenario Outline: New and lookup s3 buckets and services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate

    Examples:
      | file_path          | override_file                              |
      | use-cases/blog.yml | use-cases/s3/lookup_use_create_buckets.yml |
