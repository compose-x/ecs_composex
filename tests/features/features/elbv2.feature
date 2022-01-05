Feature: ecs_composex.elbv2

    @elbv2

    Scenario Outline: Create ELBv2 with multiple listeners and rules
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                   | override_file                     |
            | use-cases/blog.features.yml | use-cases/elbv2/create_no_acm.yml |


    @elbv2 @acm

    Scenario Outline: Create ELBv2 with ACM and DNS settings
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                   | override_file                               |
            | use-cases/blog.features.yml | use-cases/elbv2/create_only.yml             |
            | use-cases/blog.features.yml | use-cases/elbv2/create_acm_parameters.yml   |
            | use-cases/blog.features.yml | use-cases/elbv2/create_only_with_oidc.yml   |
            | use-cases/blog.features.yml | use-cases/elbv2/create_only_with_record.yml |
            | use-cases/blog.features.yml | use-cases/elbv2/create_only_with_alarms.yml |

    @elbv2 @alarms
    Scenario Outline: ELBv2 with alarms mis-configured
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose expecting an error

        Examples:
            | file_path                   | override_file                                                |
            | use-cases/blog.features.yml | use-cases/elbv2/negative-testing/create_only_with_alarms.yml |
