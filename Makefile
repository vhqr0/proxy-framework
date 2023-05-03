lint: flake8 mypy
format: yapf isort

mypy:
	mypy --ignore-missing-imports --check-untyped-defs -m proxy.manager
	mypy --ignore-missing-imports --check-untyped-defs -m proxy.contrib.proxy
	mypy --ignore-missing-imports --check-untyped-defs -m proxy.contrib.v2rayn
	mypy --ignore-missing-imports --check-untyped-defs -m proxy.contrib.tls13

flake8:
	flake8 proxy

yapf:
	yapf -i -r proxy

isort:
	isort proxy

build:
	python3 -m build

viz:
	pyreverse -m n -k --colorized -o png proxy
