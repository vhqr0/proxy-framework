lint: flake8 mypy
format: yapf isort

mypy:
	mypy --ignore-missing-imports --check-untyped-defs manage.py
	mypy --ignore-missing-imports --check-untyped-defs -m p3.contrib.tls13

flake8:
	flake8 p3

yapf:
	yapf -i -r p3

isort:
	isort p3

build:
	python3 -m build

viz:
	pyreverse -m n -k --colorized -o png p3
