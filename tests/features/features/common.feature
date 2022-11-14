Feature: common

    @logging
    Scenario Outline: Logging override
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        Examples:
            | file_path                   | override_file                    |
            | use-cases/blog.features.yml | use-cases/logging/variations.yml |

    @ecs-plugin-support
    Scenario Outline: ECS Plugin support
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        Examples:
            | file_path                   | override_file                                    |
            | use-cases/blog.features.yml | use-cases/ecs_plugin_support/blog.features.x.yml |

    @networking
    Scenario Outline: Service to Service ingress
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                   | override_file                               |
            | use-cases/blog.features.yml | use-cases/ecs/service_to_service.yml        |
            | use-cases/blog.features.yml | use-cases/ecs/service_to_service_depend.yml |

    @codeguru
    Scenario Outline: CodeGuru profiler
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                   | override_file                    |
            | use-cases/blog.features.yml | use-cases/codeguru/top_level.yml |
