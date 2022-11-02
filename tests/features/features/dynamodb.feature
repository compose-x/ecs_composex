Feature: ecs_composex.dynamodb

    @dynamodb
    Scenario Outline: Working dynamodb docker-compose files
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                                   |
            | use-cases/blog.features.yml | use-cases/dynamodb/table_with_gsi.yml                           |
            | use-cases/blog.features.yml | use-cases/dynamodb/table_with_gsi_autoscaling.yml               |
            | use-cases/blog.features.yml | use-cases/dynamodb/table.yml                                    |
            | use-cases/blog.features.yml | use-cases/dynamodb/tables.yml                                   |
            | use-cases/blog.features.yml | use-cases/dynamodb/create_lookup_legacy.yml                     |
            | use-cases/blog.features.yml | use-cases/dynamodb/create_lookup_services_mappings.yml          |
            | use-cases/blog.features.yml | use-cases/dynamodb/create_lookup_services_mappings_cloudmap.yml |
