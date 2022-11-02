Feature: ecs_composex.kms

    @kms
    Scenario Outline: Create services with a queue
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                   | override_file                       |
            | use-cases/blog.features.yml | use-cases/kms/simple_kms.yml        |
            | use-cases/blog.features.yml | use-cases/kms/create_and_lookup.yml |
