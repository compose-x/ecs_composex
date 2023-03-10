Feature: ecs_composex.services.monitoring


    @prometheus
    Scenario Outline: Services Monitoring - EMF Ingest
        Given With <file_path>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution


        Examples:
            | file_path                                       |
            | use-cases/services_monitoring/blog.features.yml |
