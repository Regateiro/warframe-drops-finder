.PHONY: lint test serve

lint:
	poetry run black -l 150 warframe tests/test_droptables.py
	poetry run flake8 --max-line-length 150 warframe tests/test_droptables.py
	poetry run isort --profile black warframe tests/test_droptables.py
	poetry run pylint --errors-only --max-line-length 150 warframe tests/test_droptables.py

test:
	poetry run pytest tests/ -v

serve:
	poetry run gunicorn -w 2 -b 127.0.0.1:8080 warframe.web:app

deploy:
	ssh ovh "cd warframe-drops-finder && git pull && poetry install"
