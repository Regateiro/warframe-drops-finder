.PHONY: lint test

lint:
	poetry run black -l 150 warframe tests/test_droptables.py
	poetry run flake8 --max-line-length 150 warframe tests/test_droptables.py
	poetry run isort --profile black warframe tests/test_droptables.py
	poetry run pylint --errors-only --max-line-length 150 warframe tests/test_droptables.py

test:
	poetry run pytest tests/ -v