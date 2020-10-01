Feature: ecs_composex.appmesh

  @compute

  Scenario Outline: I want to use EC2 With SpotFleet
    Given I use <file_path> as my docker-compose file
    And I want to use spot fleet
    Then  I render the docker-compose to composex to validate
    Examples:
      | file_path                                    |
      | use-cases/blog-all-features-with-compute.yml |

  Scenario Outline: Override using different IAM profile
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I want to use aws profile <profile_name>
    And I want to use spot fleet
    And I render the docker-compose to composex
    Then I render all files to verify execution
    Examples:
      | file_path          | override_file                                | profile_name |
      | use-cases/blog.yml | use-cases/blog-all-features.yml              | lambda       |
      | use-cases/blog.yml | use-cases/blog-all-features-with-compute.yml | preston      |
