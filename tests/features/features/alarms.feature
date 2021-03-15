Feature: ecs_composex.alarms

  @alarms
  Scenario Outline: Create services and alarms
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution


    Examples:
      | file_path                   | override_file                                  |
      | use-cases/blog.features.yml | use-cases/alarms/create_only.yml               |
      | use-cases/blog.features.yml | use-cases/alarms/create_only.with_topics.yml   |
      | use-cases/blog.features.yml | use-cases/alarms/composite_alarm.yml           |
      | use-cases/blog.features.yml | use-cases/alarms/composite_alarm.duplicate.yml |

  @alarms
  Scenario Outline: Pre-Defined alarms at service level
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    Then I render the docker-compose to composex to validate
    And I render all files to verify execution


    Examples:
      | file_path                   | override_file                 |
      | use-cases/blog.features.yml | use-cases/alarms/services.yml |

