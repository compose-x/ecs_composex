Feature: ecs_composex.elbv2

  @elbv2 @acm

  Scenario Outline: Create ELBv2 with multiple listeners and rules
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution


    Examples:
      | file_path                   | override_file                               |
      | use-cases/blog.features.yml | use-cases/elbv2/create_only.yml             |
      | use-cases/blog.features.yml | use-cases/elbv2/create_acm_parameters.yml   |
      | use-cases/blog.features.yml | use-cases/elbv2/create_no_acm.yml           |
      | use-cases/blog.features.yml | use-cases/elbv2/create_only_with_oidc.yml   |
      | use-cases/blog.features.yml | use-cases/elbv2/create_only_with_record.yml |
