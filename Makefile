.PHONY: clean clean-test clean-pyc clean-build docs help lint conform release-test release
.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-build clean-pyc clean-test clean-c9 ## remove all build, test, coverage and Python artifacts

clean-c9:
	find . -type f -name ".~c9*.py" -print -delete

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -type d -name '*.egg-info' -exec rm -fr {} +
	find . -type d -name '*.egg' -exec rm -rf {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

lint: ## check style with flake8
	flake8 ecs_composex --exclude .git,_invoke*

lint-tests:
	flake8 tests --exclude .git,_invoke*

test: ## run tests quickly with the default Python
	pytest -vv -s -x

test-all: ## run tests on every Python version with tox
	tox --skip-missing-interpreters

coverage: ## check code coverage quickly with the default Python
	coverage run --source ecs_composex -m pytest
	coverage report -m
	coverage html
	$(BROWSER) htmlcov/index.html

docs: clean-c9 ## generate Sphinx HTML documentation, including API docs
	rm -f docs/ecs_composex.rst
	rm -f docs/modules.rst
	find docs -name "ecs_composex.*.rst" -print -delete
	sphinx-apidoc -o docs/ ecs_composex
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(BROWSER) docs/_build/html/index.html

servedocs: docs ## compile the docs watching for changes
	watchmedo shell-command -p '*.rst' -c '$(MAKE) -C docs html' -R -D .

release: dist ## package and upload a release
	twich check dist/*
	twine upload dist/*

release-test: dist ## package and upload a release
	twine check dist/* || echo Failed to validate release
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*


dist: clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

install: clean ## install the package to the active Python's site-packages
	python setup.py install

conform	: ## Conform to a standard of coding syntax
	black ecs_composex tests
