Feature: ecs_composex.sqs

    @sqs
    Scenario Outline: Create services with a queue
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        And I want to upload files to S3 bucket <bucket_name>
        Then I render all files to verify execution

        Examples:
            | file_path                   | override_file                       | bucket_name                         |
            | use-cases/blog.features.yml | use-cases/sqs/create_and_lookup.yml | ecs-composex-373709687836-eu-west-1 |

    Scenario Outline: Create services with a queue
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                   | override_file                                          |
            | use-cases/blog.features.yml | use-cases/sqs/simple_queue.yml                         |
            | use-cases/blog.features.yml | use-cases/sqs/create_and_lookup.yml                    |
            | use-cases/blog.features.yml | use-cases/sqs/create_and_lookup_with_return_values.yml |
            | use-cases/blog.features.yml | use-cases/sqs/no_access.yml                            |
