Feature: ecs-firelens


    @firelens
    Scenario Outline: ECS FireLens with advanced FireHose
        Given With <file_path>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                                                        |
            | use-cases/firelens/advanced_firehose/test_advanced_firehose.yaml |
