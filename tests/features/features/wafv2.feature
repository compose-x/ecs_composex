Feature: ecs_composex.wafv2_webacl

    @wafv2_webacl
    Scenario Outline: WAFv2 WebAcl
        Given With <file_path>
        And With <override_file>
        And I use defined files as input to define execution settings
        Then I render the docker-compose to composex to validate
        And I render all files to verify execution

        Examples:
            | file_path                   | override_file                                      |
            | use-cases/blog.features.yml | use-cases/wafv2_webacl/create_only.yaml            |
#            | use-cases/blog.features.yml | use-cases/wafv2_webacl/lookup_only.yaml            |
            | use-cases/blog.features.yml | use-cases/wafv2_webacl/create_only_with_elbv2.yaml |
#            | use-cases/blog.features.yml | use-cases/wafv2_webacl/lookup_only_with_elbv2.yaml |
