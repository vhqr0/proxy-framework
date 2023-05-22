# build

.PHONY: build
build:
	python3 -m build

.PHONY: install
install:
	python3 -m pip install dist/p3-0.0.1.tar.gz

# viz

.PHONY: viz
viz:
	pyreverse -m n -k --colorized -o png p3

# lint

.PHONY: lint
lint: flake8 mypy

.PHONY: mypy
mypy:
	mypy --ignore-missing-imports --check-untyped-defs -m p3.all

.PHONY: flake8
flake8:
	flake8 p3

# format

.PHONY: format
format: yapf isort

.PHONY: yapf
yapf:
	yapf -i -r p3

.PHONY: isort
isort:
	isort p3
