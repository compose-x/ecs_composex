Feature: ecs_composex.appmesh

  @appmesh
  Scenario Outline: Mesh created with the services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I want to create a VPC
    And I want to create a Cluster
    And I render the docker-compose to composex
    Then I should have a mesh created

    Examples:
      | file_path                   | override_file                  |
      | use-cases/blog.features.yml | use-cases/appmesh/new_mesh.yml |

  @appmesh
  Scenario Outline: Shared or existing mesh
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Given I use <file_path> as my docker-compose file
    And I want to create a VPC
    And I want to create a Cluster
    Then I render the docker-compose to composex to validate
    Examples:
      | file_path                   | override_file                     |
      | use-cases/blog.features.yml | use-cases/appmesh/shared_mesh.yml |
      | use-cases/blog.features.yml | use-cases/appmesh/allow_all.yml   |

  @appmesh
  Scenario Outline: Meshes are incorrect
    Given I use <file_path> as my docker-compose file
    And I want to create a VPC
    Then I should get error raised
    Examples:
      | file_path                                                    |
      | use-cases/appmesh/negative-testing/router_route.yml          |
      | use-cases/appmesh/negative-testing/router_route_02.yml       |
      | use-cases/appmesh/negative-testing/router_service.yml        |
      | use-cases/appmesh/negative-testing/missing_node_settings.yml |
