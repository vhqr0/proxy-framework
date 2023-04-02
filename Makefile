lint: flake8 mypy

mypy:
	mypy --ignore-missing-imports --check-untyped-defs -m proxy.manager

flake8:
	flake8 proxy

yapf:
	yapf -i -r proxy

build:
	python3 -m build

viz:
	pyreverse -m n -k --colorized -o png proxy
