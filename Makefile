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

install:
	@echo "Run these commands on the server:"
	@echo ""
	@echo "  cd warframe-drops-finder"
	@echo "  cp .env.example .env  # Edit .env with PORT=3333"
	@echo "  cat << 'EOF' | sudo tee /etc/systemd/system/warframe.service"
	@echo "  [Unit]"
	@echo "  Description=Warframe Drops Finder Webserver"
	@echo ""
	@echo "  [Service]"
	@echo "  User=root"
	@echo "  WorkingDirectory=/root/warframe-drops-finder"
	@echo "  Environment=\"WEB_ROOT=/warframe\""
	@echo "  ExecStart=/root/.local/bin/poetry run gunicorn -w 2 warframe.web:app"
	@echo "  Restart=always"
	@echo ""
	@echo "  [Install]"
	@echo "  WantedBy=multi-user.target"
	@echo "  EOF"
	@echo ""
	@echo "  sudo systemctl daemon-reload"
	@echo "  sudo systemctl enable warframe.service"
	@echo "  sudo systemctl restart warframe.service"

deploy:
	ssh ovh "cd warframe-drops-finder && git pull && poetry lock && poetry install"