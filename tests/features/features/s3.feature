Feature: ecs_composex.s3

    @s3 @cleanup_context
    Scenario Outline: New s3 buckets and x-kms:: mapping
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                              |
            | use-cases/blog.features.yml | use-cases/s3/simple_s3_bucket_with_kms.yml |

    @cleanup_context
    Scenario Outline:New s3 buckets and services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                                 |
            | use-cases/blog.features.yml | use-cases/s3/simple_s3_bucket.yml                             |
            | use-cases/blog.features.yml | use-cases/s3/full_s3_bucket_properties.yml                    |
            | use-cases/blog.features.yml | use-cases/s3/lookup_use_create_buckets_services_mappings.yaml |

    @cleanup_context
    Scenario Outline: New and lookup s3 buckets and services
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate

        Examples:
            | file_path                   | override_file                                                          |
            | use-cases/blog.features.yml | use-cases/s3/lookup_use_create_buckets.yml                             |
            | use-cases/blog.features.yml | use-cases/s3/lookup_use_create_buckets_services_mappings_cloudmap.yaml |

    @cleanup_context
    Scenario Outline: New bucket and new SQS Queue with S3 notifications
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render all files to verify execution

        Examples:
            | file_path                   | override_file                              |
            | use-cases/blog.features.yml | use-cases/s3/bucket_with_notifications.yml |

    @cleanup_context
    Scenario Outline: NLookup s3 buckets only
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                |
            | use-cases/blog.features.yml | use-cases/s3/lookup_only.yml |
