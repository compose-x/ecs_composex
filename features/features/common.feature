Feature: ecs_composex.sqs
  @common
  Scenario Outline: Create services stack
    Given I use <file_path> as my docker-compose file
    And I want to upload files to S3 bucket <bucket_name>
    And I process and render the queues
    And I want to deploy to CFN stack named test
    Then I should have a stack ID

    Examples:
    |file_path|bucket_name|
    |use-cases/sqs/simple_queue.yml|ecs-composex-373709687836-eu-west-1|

  @common
  Scenario Outline: Update services services stack
    Given I use <file_path> as my docker-compose file
    And I want to upload files to S3 bucket <bucket_name>
    And I process and render the queues
    And I want to update to CFN stack named test
    Then I should have a stack ID

    Examples:
    |file_path|bucket_name|
    |use-cases/sqs/simple_queue.yml|ecs-composex-373709687836-eu-west-1|

  @common
  Scenario Outline: Update stack in a failed stack
    Given I use <file_path> as my docker-compose file
    And I want to upload files to S3 bucket <bucket_name>
    And I process and render the queues
    And I want to update a failed stack named test
    Then I should not have a stack ID

    Examples:
    |file_path|bucket_name|
    |use-cases/sqs/simple_queue.yml|ecs-composex-373709687836-eu-west-1|
