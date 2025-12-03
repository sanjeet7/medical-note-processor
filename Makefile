.PHONY: build rebuild run stop test clean logs help

# =============================================================================
# Quick Start Commands
# =============================================================================

build:  ## Build and initialize (skips if DB/index already exist)
	@echo "🔨 Building and initializing..."
	@echo "   (Skips seeding/indexing if already done)"
	@echo ""
	docker-compose up --build -d
	@echo ""
	@echo "⏳ Running ingestion pipeline (seeding DB, indexing guidelines)..."
	@echo "   This may take 2-5 minutes on first run."
	@echo "   Showing logs below (Ctrl+C to stop logs, container keeps running):"
	@echo ""
	@docker-compose logs -f api &
	@while ! curl -s http://localhost:8000/health > /dev/null 2>&1; do \
		sleep 3; \
	done
	@pkill -f "docker-compose logs" 2>/dev/null || true
	@echo ""
	@echo "✅ Build complete! API is ready."
	@echo "   API: http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"

rebuild:  ## Force rebuild: re-seed DB and re-index guidelines
	@echo "🔨 Rebuilding with fresh initialization..."
	@echo ""
	FORCE_INIT=true docker-compose up --build -d
	@echo ""
	@echo "⏳ Running ingestion pipeline (re-seeding DB, re-indexing guidelines)..."
	@echo "   This may take 2-5 minutes."
	@echo "   Showing logs below (Ctrl+C to stop logs, container keeps running):"
	@echo ""
	@docker-compose logs -f api &
	@while ! curl -s http://localhost:8000/health > /dev/null 2>&1; do \
		sleep 3; \
	done
	@pkill -f "docker-compose logs" 2>/dev/null || true
	@echo ""
	@echo "✅ Rebuild complete! API is ready."
	@echo "   API: http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"

run:  ## Start the application (quick, no build)
	@echo "🚀 Starting Medical Note Processor..."
	docker-compose up -d
	@echo ""
	@echo "✅ Started! API: http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"

stop:  ## Stop all services
	@echo "Stopping services..."
	docker-compose down
	@echo "✅ Stopped"

logs:  ## View application logs
	docker-compose logs -f api

clean:  ## Stop services and remove all data (volumes, images)
	@echo "🧹 Cleaning up..."
	docker-compose down -v --rmi local 2>/dev/null || true
	rm -rf __pycache__ .pytest_cache data/faiss_db
	rm -rf test.db test_*.db
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "__pycache__" -type d -delete 2>/dev/null || true
	@echo "✅ Cleaned"

# =============================================================================
# Testing
# =============================================================================

test:  ## Run all tests
	docker-compose exec api pytest tests/ -v || \
		(echo "Container not running. Starting..." && \
		docker-compose up -d && sleep 5 && \
		docker-compose exec api pytest tests/ -v)

test-part1:  ## Test Part 1: Backend
	docker-compose exec api pytest tests/test_part1.py -v

test-part2:  ## Test Part 2: LLM Integration
	docker-compose exec api pytest tests/test_part2.py -v

test-part3:  ## Test Part 3: RAG Pipeline
	docker-compose exec api pytest tests/test_part3.py -v

test-part4:  ## Test Part 4: Agent System
	docker-compose exec api pytest tests/test_part4.py -v

test-part5:  ## Test Part 5: FHIR Conversion
	docker-compose exec api pytest tests/test_part5.py -v

# =============================================================================
# Help
# =============================================================================

help:  ## Show this help
	@echo "Medical Note Processor - Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make build            Build and initialize (skips if already done)"
	@echo "  make rebuild          Force fresh DB seed and guideline indexing"
	@echo ""
	@echo "Running:"
	@echo "  make run              Start the application"
	@echo "  make stop             Stop all services"
	@echo "  make logs             View application logs"
	@echo "  make clean            Remove all data and containers"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-part1       Test Part 1: Backend"
	@echo "  make test-part2       Test Part 2: LLM"
	@echo "  make test-part3       Test Part 3: RAG"
	@echo "  make test-part4       Test Part 4: Agent"
	@echo "  make test-part5       Test Part 5: FHIR"
