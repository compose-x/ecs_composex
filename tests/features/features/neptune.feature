Feature: ecs_composex.neptune

    @neptune @create
    Scenario Outline: Simple OS Domain with services
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        And I render the docker-compose to composex
        Then I render all files to verify execution

        Examples:
            | file_path                   | override_file                      |
            | use-cases/blog.features.yml | use-cases/neptune/create_only.yaml |
