Feature: ecs-cluster


    @cluster
    Scenario Outline: ECS Cluster override
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        Examples:
            | file_path                   | override_file                                  |
            | use-cases/blog.features.yml | use-cases/ecs/cluster_create.yml               |
            | use-cases/blog.features.yml | use-cases/ecs/cluster_lookup.yml               |
            | use-cases/blog.features.yml | use-cases/ecs/cluster_lookup_with_logging.yaml |
            | use-cases/blog.features.yml | use-cases/ecs/cluster_create_with_logging.yml  |

    @cluster
    Scenario Outline: ECS Capacity Providers adapt or auto-correct
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                                      |
            | use-cases/blog.features.yml | use-cases/ecs/cluster_lookup_and_capacity_providers.yml            |
            | use-cases/blog.features.yml | use-cases/ecs/cluster_lookup_and_cluster_no_capacity_providers.yml |
            | use-cases/blog.features.yml | use-cases/ecs/negative_testing/invalid_capacity_provider.yml       |

    @cluster
    Scenario Outline: ECS services with invalid compute settings
        Given With <file_path>
        And With <override_file>
        Then I use defined files as input expecting an error

        Examples:
            | file_path                   | override_file                                          |
            | use-cases/blog.features.yml | use-cases/ecs/negative_testing/services_multi_arch.yml |
            | use-cases/blog.features.yml | use-cases/ecs/negative_testing/services_multi_os.yml   |
