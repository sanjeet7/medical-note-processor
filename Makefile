.PHONY: setup test run clean db-up db-down seed index-guidelines

# ============================================================================
# Setup & Installation
# ============================================================================

setup:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp .env.example .env

# ============================================================================
# Testing
# ============================================================================

test:
	. venv/bin/activate && pytest tests/ -v

test-part1:
	. venv/bin/activate && pytest tests/test_part1.py -v

test-part2:
	. venv/bin/activate && pytest tests/test_part2.py tests/test_llm_connection.py -v

test-part3:
	. venv/bin/activate && pytest tests/test_part3.py -v

test-part4:
	. venv/bin/activate && pytest tests/test_part4.py -v

test-part4-unit:
	@echo "Running Part 4 unit tests (mocked APIs)..."
	. venv/bin/activate && pytest tests/test_part4.py -v -k "not TestRealNIHAPIs and not TestGoldenSetEvaluation"

test-part4-api:
	@echo "Running Part 4 real NIH API integration tests..."
	. venv/bin/activate && pytest tests/test_part4.py::TestRealNIHAPIs -v -s

test-part4-golden:
	@echo "Running Part 4 golden set evaluation (requires OpenAI API key)..."
	. venv/bin/activate && pytest tests/test_part4.py::TestGoldenSetEvaluation -v -s

test-llm-connection:
	. venv/bin/activate && pytest tests/test_llm_connection.py -v

test-unit:
	@echo "Running all unit tests (fast, mocked)..."
	. venv/bin/activate && pytest tests/ -v -k "not TestRealNIHAPIs and not TestGoldenSetEvaluation and not TestRAGEvaluation"

test-integration:
	@echo "Running integration tests (real APIs)..."
	. venv/bin/activate && pytest tests/test_part4.py::TestRealNIHAPIs -v -s

# ============================================================================
# Database & Infrastructure
# ============================================================================

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

# ============================================================================
# Running the Application
# ============================================================================

run: seed index-guidelines
	. venv/bin/activate && uvicorn src.main:app --reload

run-dev:
	. venv/bin/activate && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# ============================================================================
# Cleanup
# ============================================================================

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf data/faiss_db
	rm -rf test.db test_part4.db
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -delete

# ============================================================================
# Help
# ============================================================================

help:
	@echo "Medical Note Processor - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              - Create venv, install deps, copy .env"
	@echo ""
	@echo "Testing:"
	@echo "  make test               - Run all tests"
	@echo "  make test-unit          - Run unit tests only (fast, mocked)"
	@echo "  make test-integration   - Run integration tests (real NIH APIs)"
	@echo "  make test-part1         - Run Part 1 tests (Backend)"
	@echo "  make test-part2         - Run Part 2 tests (LLM)"
	@echo "  make test-part3         - Run Part 3 tests (RAG)"
	@echo "  make test-part4         - Run Part 4 tests (Agent)"
	@echo "  make test-part4-unit    - Run Part 4 unit tests only"
	@echo "  make test-part4-api     - Run Part 4 real NIH API tests"
	@echo "  make test-part4-golden  - Run Part 4 golden set evaluation"
	@echo ""
	@echo "Database:"
	@echo "  make db-up              - Start PostgreSQL container"
	@echo "  make db-down            - Stop PostgreSQL container"
	@echo "  make seed               - Seed database with SOAP notes"
	@echo "  make index-guidelines   - Index medical guidelines for RAG"
	@echo ""
	@echo "Running:"
	@echo "  make run                - Start the application (with seed + index)"
	@echo "  make run-dev            - Start in development mode"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean              - Remove cache and temp files"
