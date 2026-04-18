.PHONY: serve deploy lint test

lint:
	@echo "\nRunning code quality checks..."
	@poetry run black -l 150 ./warframe/*.py
	@poetry run flake8 --max-line-length 150 ./warframe/*.py
	@poetry run isort --profile black ./warframe/*.py
	@poetry run pylint --errors-only --max-line-length 150 ./warframe/*.py

serve:
	@poetry run gunicorn -w 2 warframe.web:app

test: lint
	@echo "\nRunning tests..."
	@poetry run pytest tests/ -v

deploy: test
	@echo "\nDeploying..."
	@ssh ovh "cd warframe-drops-finder && git pull && poetry lock && poetry install && sudo systemctl restart warframe.service" >/dev/null