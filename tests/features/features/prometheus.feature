Feature: ecs_composex.prometheus


    @prometheus
    Scenario Outline: Prometheus and ECS Insights
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                              | override_file                                      |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_enabled.yml        |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_custom_options.yml |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_config_file.yml    |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_enabled.yml        |
