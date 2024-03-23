Feature: community

    @warpstream
    Scenario Outline: WarpStream
        Given I use <file_path> as my docker-compose file
        Then I render the docker-compose to composex to validate
        Examples:
            | file_path                 |
            | use-cases/warpstream.yaml |
