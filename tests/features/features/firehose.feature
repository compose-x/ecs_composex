Feature: ecs_composex.firehose

    @firehose
    Scenario Outline: Create services with a queue
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
#        Then I render the docker-compose to composex to validate
        Then I render all files to verify execution


        Examples:
            | file_path                   | override_file                      |
            | use-cases/blog.features.yml | use-cases/firehose/create_only.yml |
            | use-cases/blog.features.yml | use-cases/firehose/lookup_only.yml |
