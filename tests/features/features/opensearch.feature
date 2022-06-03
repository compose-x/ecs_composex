Feature: ecs_composex.opensearch

    @opensearch @create
    Scenario Outline: Simple OS Domain with services
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        And I render the docker-compose to composex
        Then I render all files to verify execution

        Examples:
            | file_path                   | override_file                                |
            | use-cases/blog.features.yml | use-cases/opensearch/create_only.yaml        |
            | use-cases/blog.features.yml | use-cases/opensearch/create_only_single.yaml |

    @opensearch @errors
    Scenario Outline: Negative tests for simple OS Domain with services
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose expecting an error
#        Then I render all files to verify execution

        Examples:
            | file_path                   | override_file                                                      |
            | use-cases/blog.features.yml | use-cases/opensearch/negative_testing/incompatible_parameters.yaml |
            | use-cases/blog.features.yml | use-cases/opensearch/negative_testing/unsupported_config.yaml      |
            | use-cases/blog.features.yml | use-cases/opensearch/negative_testing/unsupported_version.yaml     |
