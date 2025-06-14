Feature: ecs_composex.vpc

    @vpc
    Scenario Outline: Various VPC settings
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                   | override_file                           |
            | use-cases/blog.features.yml | use-cases/vpc/new_vpc.yml               |
            | use-cases/blog.features.yml | use-cases/vpc/new_with_flowlogs.yml     |
            | use-cases/blog.features.yml | use-cases/vpc/no_nats_no_endpoints.yaml |

    Scenario Outline: VPC Lookup
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution
        Examples:
            | file_path                   | override_file                          |
            | use-cases/blog.features.yml | use-cases/vpc/lookup_vpc_via_tags.yaml |
            | use-cases/blog.features.yml | use-cases/vpc/lookup_vpc_via_arn.yaml  |
            | use-cases/blog.features.yml | use-cases/vpc/lookup_vpc_via_id.yaml   |
