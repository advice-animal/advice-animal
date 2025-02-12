PYTHON?=python
SOURCES=advice_animal setup.py

UV:=$(shell uv --version)
ifdef UV
	VENV:=uv venv
	PIP:=uv pip
else
	VENV:=python -m venv
	PIP:=python -m pip
endif

.PHONY: venv
venv:
	$(VENV) .venv
	source .venv/bin/activate && make setup
	@echo 'run `source .venv/bin/activate` to use virtualenv'

# The rest of these are intended to be run within the venv, where python points
# to whatever was used to set up the venv.

.PHONY: setup
setup:
	$(PIP) install -Ue .[dev,test]

.PHONY: test
test:
	python -m coverage run -m pytest $(TESTOPTS)
	python -m coverage report

.PHONY: format
format:
	ruff format .
	ruff check --fix .

.PHONY: lint
lint:
	ruff check .
	python -m checkdeps --allow-names advice_animal advice_animal
	mypy --strict --install-types --non-interactive advice_animal

.PHONY: release
release:
	rm -rf dist
	python setup.py sdist bdist_wheel
	twine upload dist/*
