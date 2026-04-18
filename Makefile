.PHONY: lint test serve install deploy

lint:
	poetry run black -l 150 warframe tests/test_droptables.py
	poetry run flake8 --max-line-length 150 warframe tests/test_droptables.py
	poetry run isort --profile black warframe tests/test_droptables.py
	poetry run pylint --errors-only --max-line-length 150 warframe tests/test_droptables.py

test:
	poetry run pytest tests/ -v

serve:
	poetry run gunicorn -w 2 warframe.web:app

deploy:
	ssh ovh "cd warframe-drops-finder && git pull && poetry lock && poetry install && sudo systemctl restart warframe.service"