
.. meta::
    :description: ECS Compose-X AWS Cognito UserPool syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Cognito

.. _cognito_userpool_syntax_reference:

======================
x-cognito_userpool
======================

This module allows you to identify through Lookup the Cognito Userpool you wish to us in x-elbv2.

For now this module is of limited use, but will be soon extended to all capabilities (Create/Use)

Syntax Reference
=================

.. code-block:: yaml

    x-cognito_userpool:
      userpool-with-saml:
        Lookup:
          Tags:
            - application: kafdrop
            - saml_provider: someone

Examples
=========

.. code-block:: yaml
    :caption: Example with x-elbv2 for ALB integration.

    x-cognito_userpool:
      kafdrop-pool:
        Lookup:
          Tags:
            - application: kafdrop

    x-elbv2:
      kafdrop-cc-scAlb:
        Settings:
          Subnets: PublicSubnets
        Properties:
          Scheme: internet-facing
          Type: application
        MacroParameters:
          Ingress:
            ExtSources:
              - IPv4: 0.0.0.0/0
                Name: ANY
                Description: ANY
        Listeners:
          - Port: 80
            Protocol: HTTP
            DefaultActions:
              - Redirect: HTTP_TO_HTTPS
          - Port: 443
            Protocol: HTTPS
            SslPolicy: ELBSecurityPolicy-FS-1-2-Res-2020-10
            Certificates:
              - x-acm: kafdrop-certs
            Targets:
              - name: akhq:akhq-nginx
                access: /
                CreateCognitoClient:
                  UserPoolId: kafdrop-pool
                  GenerateSecret: true
                  AllowedOAuthScopes:
                    - email
                    - profile
                    - openid
                  AllowedOAuthFlows:
                    - code
                  CallbackURLs:
                    - https://kafdropmydomain.net/oauth2/idpresponse
                  DefaultRedirectURI: https://kafdropmydomain.net/oauth2/idpresponse
                  EnableTokenRevocation: true
                  ExplicitAuthFlows:
                    - ALLOW_USER_SRP_AUTH
                    - ALLOW_REFRESH_TOKEN_AUTH
                  AccessTokenValidity: 1
                  RefreshTokenValidity: 1
                  AllowedOAuthFlowsUserPoolClient: true
                  WriteAttributes:
                    - email
                    - family_name
                    - given_name
                    - name
                    - nickname
                    - profile
                  ReadAttributes:
                    - email
                    - family_name
                    - given_name
                    - name
                    - nickname
                    - profile
                  SupportedIdentityProviders:
                    - AzureSSO
                AuthenticateCognitoConfig:
                  OnUnauthenticatedRequest: authenticate
                  Scope: openid
                  SessionCookieName: kafdrop
                  SessionTimeout: 3600

        Services:
          - name: akhq:akhq-nginx
            port: 443
            protocol: HTTPS
            healthcheck: 443:HTTPS:4:2:10:5:200:/health

    x-acm:
      kafdrop-certs:
        MacroParameters:
          DomainNames:
            - kafdropmydomain.net

JSON Schema
============

Model
-----------------

.. jsonschema:: ../../../ecs_composex/cognito_userpool/x-cognito_userpool.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/cognito_userpool/x-cognito_userpool.spec.json
    :language: json
