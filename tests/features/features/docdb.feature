Feature: ecs_composex.docdb

    @docdb
    Scenario Outline: AWS DocDB creation
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                            |
            | use-cases/blog.features.yml | use-cases/docdb/create_only_legacy.yml   |
            | use-cases/blog.features.yml | use-cases/docdb/create_only.yml          |
            | use-cases/blog.features.yml | use-cases/docdb/subnets_override.yml     |
            | use-cases/blog.features.yml | use-cases/docdb/create_only_cloudmap.yml |
