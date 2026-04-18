.PHONY: serve deploy lint test

lint:
	poetry run black -l 150 ./warframe/*.py
	poetry run flake8 --max-line-length 150 ./warframe/*.py
	poetry run isort --profile black ./warframe/*.py
	poetry run pylint --errors-only --max-line-length 150 ./warframe/*.py

serve:
	poetry run gunicorn -w 2 warframe.web:app

test:
	poetry run pytest tests/ -v

deploy:
	ssh ovh "cd warframe-drops-finder && git pull && poetry lock && poetry install && sudo systemctl restart warframe.service"