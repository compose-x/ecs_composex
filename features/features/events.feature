Feature: ecs_composex.events

  @events
  Scenario Outline: Working with events tasks & services
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate

    Examples:
      | file_path                   | override_file               |
      | use-cases/blog.features.yml | use-cases/events/simple.yml |
