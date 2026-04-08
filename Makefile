.PHONY: lint test

lint:
	poetry run black -l 150 src/droptables.py tests/test_droptables.py
	poetry run flake8 --max-line-length 150 src/droptables.py tests/test_droptables.py
	poetry run isort --profile black src/droptables.py tests/test_droptables.py
	poetry run pylint --errors-only --max-line-length 150 src/droptables.py tests/test_droptables.py

test:
	PYTHONPATH=. poetry run pytest tests/ -v
