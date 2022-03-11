Feature: ecs_composex.s3

    @s3
    Scenario Outline: New s3 buckets and x-kms:: mapping
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                              |
            | use-cases/blog.features.yml | use-cases/s3/simple_s3_bucket_with_kms.yml |

    Scenario Outline:New s3 buckets and services
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                                 |
            | use-cases/blog.features.yml | use-cases/s3/simple_s3_bucket.yml                             |
            | use-cases/blog.features.yml | use-cases/s3/full_s3_bucket_properties.yml                    |
            | use-cases/blog.features.yml | use-cases/s3/lookup_use_create_buckets_services_mappings.yaml |

    Scenario Outline: New and lookup s3 buckets and services
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate

        Examples:
            | file_path                   | override_file                                                          |
            | use-cases/blog.features.yml | use-cases/s3/lookup_use_create_buckets.yml                             |
            | use-cases/blog.features.yml | use-cases/s3/lookup_use_create_buckets_services_mappings_cloudmap.yaml |


    Scenario Outline: NLookup s3 buckets only
        Given I use <file_path> as my docker-compose file and <override_file> as override file
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                |
            | use-cases/blog.features.yml | use-cases/s3/lookup_only.yml |
