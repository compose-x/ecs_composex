Feature: ecs_composex.rds

    @rds
    Scenario Outline: Simple RDS with services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                 |
            | use-cases/blog.features.yml | use-cases/rds/rds_basic.yml                   |
            | use-cases/blog.features.yml | use-cases/rds/subnets_override.yml            |
            | use-cases/blog.features.yml | use-cases/rds/rds_cluster_multi_instances.yml |
            | use-cases/blog.features.yml | use-cases/rds/rds_with_iam_access.yml         |

    @rds @lookup
    Scenario Outline: Simple RDS with services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And services have access to it

        Examples:
            | file_path                   | override_file                                            |
            | use-cases/blog.features.yml | use-cases/rds/rds_import.yml                             |
            | use-cases/blog.features.yml | use-cases/rds/rds_import_with_return_values.yml          |
            | use-cases/blog.features.yml | use-cases/rds/rds_import_with_return_values_cloudmap.yml |
