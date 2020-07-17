Feature: ecs_composex.sqs
  @sqs
  Scenario Outline: Create services with a queue
    Given I use <file_path> as my docker-compose file
    And I want to upload files to S3 bucket <bucket_name>
    And I process and render the queues
    And I want to deploy to CFN stack named test
    Then I should have a stack ID

    Examples:
    |file_path|bucket_name|
    |use-cases/sqs/simple_queue.yml|ecs-composex-373709687836-eu-west-1|

  @sqs
  Scenario Outline: Call to create sqs without SQS queues defined
    Given I use <file_path> as my docker-compose file
    And I want to deploy only SQS
    Then With missing module from file, program quits with code <code>
    Examples:
    |file_path|code|
    |use-cases/sqs/negative-testing/no_queues.yml|9|
