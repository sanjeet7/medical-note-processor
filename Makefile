.PHONY: setup test run clean db-up db-down seed index-guidelines

setup:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env

test:
	. venv/bin/activate && pytest tests/ -v

test-part1:
	. venv/bin/activate && pytest tests/test_part1.py -v

test-part2:
	. venv/bin/activate && pytest tests/test_part2.py tests/test_llm_connection.py -v

test-part3:
	. venv/bin/activate && pytest tests/test_part3.py -v

test-llm-connection:
	. venv/bin/activate && pytest tests/test_llm_connection.py -v

db-up:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Waiting for database to be ready..."
	@sleep 5

db-down:
	docker-compose -f docker-compose.dev.yml down

seed: db-up
	@echo "Checking if database needs seeding..."
	@. venv/bin/activate && python scripts/seed_database.py || echo "Database already seeded or seeding failed"

index-guidelines:
	@echo "Indexing medical guidelines into FAISS..."
	@. venv/bin/activate && python scripts/index_guidelines.py

run: seed index-guidelines
	. venv/bin/activate && uvicorn src.main:app --reload

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf data/faiss_db
	find . -name "*.pyc" -delete
