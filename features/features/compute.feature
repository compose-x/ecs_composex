Feature: ecs_composex.compute

  @compute
  Scenario Outline: I want to use EC2 With SpotFleet
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I want to use spot fleet
    Then  I render the docker-compose to composex to validate
    Examples:
      | file_path                   | override_file                        |
      | use-cases/blog.features.yml | use-cases/ec2compute/spot_config.yml |

  Scenario Outline: Override using different IAM profile
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I want to use aws profile <profile_name>
    And I want to use spot fleet
    And I render the docker-compose to composex
    Then I render all files to verify execution
    Examples:
      | file_path                   | override_file                        | profile_name |
      | use-cases/blog.features.yml | use-cases/ec2compute/spot_config.yml | preston      |
