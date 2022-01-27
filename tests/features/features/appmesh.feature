Feature: ecs_composex.appmesh

    @appmesh @create
    Scenario Outline: Mesh created with the services
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        And I render the docker-compose to composex
        Then I render all files to verify execution

        Examples:
            | file_path                   | override_file                  |
            | use-cases/blog.features.yml | use-cases/appmesh/new_mesh.yml |

    @appmesh @error
    Scenario Outline: Meshes are incorrect
        Given I use <file_path> as my docker-compose file
        And I render the docker-compose to composex
        Then I render the docker-compose expecting an error
        Examples:
            | file_path                                                    |
            | use-cases/appmesh/negative-testing/router_route.yml          |
            | use-cases/appmesh/negative-testing/router_route_02.yml       |
            | use-cases/appmesh/negative-testing/router_service.yml        |
            | use-cases/appmesh/negative-testing/missing_node_settings.yml |
