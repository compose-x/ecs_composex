Feature: ecs_composex.sns

    @sns
    Scenario Outline: SNS Topics basic tests
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                   | override_file                                |
            | use-cases/blog.features.yml | use-cases/sns/simple_sns.yml                 |
            | use-cases/blog.features.yml | use-cases/sns/create_and_lookup.yml          |
            | use-cases/blog.features.yml | use-cases/sns/sns_with_sqs_subscription.yaml |
