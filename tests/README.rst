=======================
ECS ComposeX -- Tests
=======================

In these subfolders you will find the TDD and BDD tests implemented via pytest and behave to test the execution
of ECS ComposeX CLI.

features
=========

This subfolder contains all the BDD tests done via behave.


pytests
========

Subfolder contains all the pytest unit-tests. Most of these use placebo to register the API call done the first time around,
store it and mocks during tests the API response from AWS.
