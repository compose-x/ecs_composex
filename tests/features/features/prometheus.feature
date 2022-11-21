Feature: ecs_composex.prometheus


    @prometheus
    Scenario Outline: Prometheus and ECS Insights
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                              | override_file                                      |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_enabled.yml        |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_custom_options.yml |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_config_file.yml    |
            | use-cases/prometheus/blog.features.yml | use-cases/prometheus/prometheus_enabled.yml        |
