Feature: ecs-firelens


    @firelens
    Scenario Outline: ECS FireLens with advanced FireHose
        Given I use <file_path> as my docker-compose file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                                                        |
            | use-cases/firelens/advanced_firehose/test_advanced_firehose.yaml |
