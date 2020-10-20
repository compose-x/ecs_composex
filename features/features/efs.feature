Feature: ecs_composex.efs

  @efs
  Scenario Outline: New efs and services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate

    Examples:
      | file_path          | override_file                    |
      | use-cases/blog.yml | use-cases/efs/simple_efs.yml     |
      | use-cases/blog.yml | use-cases/efs/efs_lookup_vpc.yml |
    