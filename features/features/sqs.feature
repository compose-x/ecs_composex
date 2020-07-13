Feature: ecs_composex.sqs
  @static @sqs
  Scenario Outline: Create services with a queue
    Given I use <file_path> as my docker-compose file
    Then I should have SQS queues
    And services have access to the queues

    Examples:
    |file_path|
    |use-cases/sqs/simple_queue.yml|
