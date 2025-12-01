.PHONY: setup test run clean db-up db-down

setup:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env

test:
	. venv/bin/activate && pytest tests/test_part1.py -v

db-up:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Waiting for database to be ready..."
	@sleep 5

db-down:
	docker-compose -f docker-compose.dev.yml down

seed: db-up
	. venv/bin/activate && python scripts/seed_database.py

run: seed
	. venv/bin/activate && uvicorn src.main:app --reload

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	find . -name "*.pyc" -delete
