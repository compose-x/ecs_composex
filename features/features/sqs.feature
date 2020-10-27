Feature: ecs_composex.sqs

  @sqs
  Scenario Outline: Create services with a queue
    Given I use <file_path> as my docker-compose file and <override_file> as override file
    And I want to upload files to S3 bucket <bucket_name>
    And I process and render the queues
    And I want to deploy to CFN stack named test
    Then I should have a stack ID

    Examples:
      | file_path                   | override_file                       | bucket_name                         |
      | use-cases/blog.features.yml | use-cases/sqs/create_and_lookup.yml | ecs-composex-373709687836-eu-west-1 |
