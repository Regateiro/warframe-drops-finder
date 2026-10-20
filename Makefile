.PHONY: serve deploy lint test

lint:
	@echo "Running code quality checks..."
	@poetry run black --check -l 150 ./warframe/*.py ./tests/*.py
	@poetry run flake8 --max-line-length 150 ./warframe/*.py ./tests/*.py
	@poetry run isort --check-only --profile black ./warframe/*.py ./tests/*.py
	@poetry run pylint --errors-only --max-line-length 150 ./warframe/*.py ./tests/*.py

format:
	@echo "Formatting code..."
	@poetry run black -l 150 ./warframe/*.py ./tests/*.py
	@poetry run isort --profile black ./warframe/*.py ./tests/*.py

serve:
	@poetry run gunicorn -w 2 --bind 127.0.0.1:3333 warframe.web:app

test: lint
	@echo ""
	@echo "Running tests..."
	@poetry run pytest tests/ -v

deploy: test
	@echo ""
	@echo "Deploying..."
	@ssh ovh "cd warframe-drops-finder && git pull && poetry lock && poetry install && sudo systemctl restart warframe.service" >/dev/null
