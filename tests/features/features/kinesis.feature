Feature: ecs_composex.kinesis

    @kinesis
    Scenario Outline: Create services with a queue
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                   | override_file                            |
            | use-cases/blog.features.yml | use-cases/kinesis/create_only.yml        |
            | use-cases/blog.features.yml | use-cases/kinesis/create_only_kcl.yml    |
#      | use-cases/blog.features.yml | use-cases/kinesis/create_lookup.yml |
