CPU_COUNT=$(shell python3 -c "from multiprocessing import cpu_count; print(cpu_count())")

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help            to show this message"
	@echo "  install-linters to install linters."
	@echo "  lint            to run all linters"
	@echo "  lint-flake8     to run the flake8 linter"
	@echo "  lint-pylint     to run the pylint linter"

# It is assumed that a virtualenv is available to install the required linters.
install-linters:
	pip install -q flake8 flake8-docstrings flake8-quotes pydocstyle pylint

# This is just a tool to ease the use of linters on functional tests dir.
lint: lint-flake8 lint-pylint

# E501 and F401 are ignored because Pylint performs similar checks.
lint-flake8:
	flake8 . --ignore E501,F401

lint-pylint:
	pylint -j $(CPU_COUNT) --reports=n --disable=I api/

.PHONY: help lint lint-flake8 lint-pylint install-linters
