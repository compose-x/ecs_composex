Feature: ecs_composex.neptune

    @neptune @create
    Scenario Outline: Simple OS Domain with services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                      |
            | use-cases/blog.features.yml | use-cases/neptune/create_only.yaml |
