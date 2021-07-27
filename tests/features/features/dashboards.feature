Feature: ecs_composex.dashboards

    @dashboards
    Scenario Outline: Dashboards
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                    |
            | use-cases/blog.features.yml | use-cases/dashboards/simple.yaml |
