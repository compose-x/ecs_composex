Feature: ecs_composex.events

    @events
    Scenario Outline: Working with events tasks & services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                  |
            | use-cases/blog.features.yml | use-cases/events/simple.yml                    |
            | use-cases/blog.features.yml | use-cases/events/mixed.yml                     |
            | use-cases/blog.features.yml | use-cases/events/multi_rules_same_service.yaml |

    @events
    Scenario Outline: LEGACY Working with events tasks & services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                      |
            | use-cases/blog.features.yml | use-cases/events/simple_legacy.yml |
            | use-cases/blog.features.yml | use-cases/events/mixed_legacy.yml  |
