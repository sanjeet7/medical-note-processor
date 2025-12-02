# Medical Note Processing System - README

> **Part of take-home assessment for healthcare AI engineer position**

Complete implementation guide for a production-grade medical note processing system with FastAPI, RAG, agent-based extraction, FHIR conversion, and comprehensive testing.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Getting Started](#getting-started)
- [Implementation Plan](#implementation-plan)
- [Testing](#testing)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)

---

## 🎯 Overview

This system automates medical document processing workflows through:
- **FastAPI backend** with PostgreSQL database
- **LLM integration** for summarization (provider-agnostic: OpenAI, Ollama)
- **RAG pipeline** for medical guideline Q&A
- **Agent-based extraction** with NIH API integration (ICD-10, RxNorm)
- **FHIR conversion** using fhir.resources library
- **Docker deployment** with docker-compose

---

## ✨ Features

### Part 1: FastAPI Backend
- ✅ Health check endpoint
- ✅ Full- **CRUD Operations**: Full create, read, update, delete support with validation
- **Partial Updates**: PUT endpoint supports updating only specific fields
- **Database Seeding**: 6 sample SOAP notes included

### Part 2 LLM Integration:
- OpenAI and Anthropic provider support
- `/summarize_note` - Summarize medical notes using LLM
- `/query_note` - Ask specific questions about medical notes
- Response caching to reduce API costs
- Document ID or raw text input support

### Part 3: RAG Pipeline
- ✅ Medical guidelines knowledge base
- ✅ Smart chunking (500 tokens, 100 overlap)
- ✅ ChromaDB vector store
- ✅ LLM-based reranking
- ✅ Source citations in answers

### Part 4: Agent System
- ✅ Entity extraction (patient, conditions, medications, vitals)
- ✅ ICD-10 code lookup via NIH API
- ✅ RxNorm code lookup via NIH API
- ✅ Trajectory logging
- ✅ Comprehensive unit tests

### Part 5: FHIR Conversion
- ✅ FHIR resource mapping (Patient, Condition, MedicationRequest, Observation, Procedure, CarePlan)
- ✅ FHIR Bundle creation
- ✅ Spec-compliant using fhir.resources library

### Part 6: Containerization
- ✅ Multi-stage Dockerfile
- ✅ Docker Compose orchestration
- ✅ Database persistence
- ✅ Auto-seeding and indexing
- ✅ Hot-reloading for development
- ✅ Makefile for common operations

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API key (or local Ollama instance)

### Setup

1. **Clone & Navigate**
```bash
cd medical_note_processor
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

3. **Build & Start**
```bash
make build
make up
```

4. **Verify**
```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# View logs
make logs
```

### First Steps

```bash
# 1. Check seeded documents
curl http://localhost:8000/documents

# 2. Summarize a medical note
curl -X POST http://localhost:8000/summarize_note \
  -H "Content-Type: application/json" \
  -d '{"text": "Patient presents with chest pain. BP 140/90, HR 88. Prescribed aspirin."}'

# 3. Ask a medical question (RAG)
curl -X POST http://localhost:8000/answer_question \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the first-line treatment for hyperlipidemia?"}'

# 4. Extract structured data from SOAP note
curl -X POST http://localhost:8000/extract_structured \
  -H "Content-Type: application/json" \
  -d @data/soap_notes/soap_02.txt

# 5. Convert to FHIR (use output from step 4 as input)
```

---

## 📚 Implementation Plan

Detailed implementation plans available:

- **[implementation_plan.md](./implementation_plan.md)** - Parts 1-3 (Backend, LLM, RAG)
- **[implementation_plan_parts_4_6.md](./implementation_plan_parts_4_6.md)** - Parts 4-6 (Agent, FHIR, Docker)

Each part includes:
- Requirements checklist (core + stretch goals)
- Complete code implementation
- Unit and integration tests
- Manual testing instructions
- Validation checklist

---

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Test Individual Parts
```bash
# Part 1: Backend
docker-compose exec api pytest tests/test_part1.py -v

# Part 2: LLM
docker-compose exec api pytest tests/test_part2.py -v

# Part 3: RAG
docker-compose exec api pytest tests/test_part3.py -v

# Part 4: Agent
docker-compose exec api pytest tests/test_part4.py -v

# Part 5: FHIR
docker-compose exec api pytest tests/test_part5.py -v

# Part 6: Docker
pytest tests/test_part6.py -v
```

### Custom Evaluations
```bash
# RAG evaluation (golden test set)
docker-compose exec api pytest tests/evaluation/test_rag_eval.py -v

# Agent evaluation (extraction accuracy, code lookup)
docker-compose exec api pytest tests/evaluation/test_agent_eval.py -v
```

### Manual Testing
See [docs/API_EXAMPLES.md](./docs/API_EXAMPLES.md) for curl examples.

---

## 📖 API Documentation

### Part 1: Core Endpoints

#### GET /health
Health check endpoint that returns system status.

**Response:**
```json
{"status": "ok"}
```

#### GET /documents
Fetch list of all document IDs.

**Response:**
```json
[1, 2, 3, 4, 5, 6]
```

#### GET /documents/{document_id}
Fetch a specific document by ID.

#### POST /documents
Create a new document.

#### PUT /documents/{document_id}
Update a document (supports partial updates).

#### DELETE /documents/{document_id}
Delete a document.

### Part 2: LLM Endpoints

#### POST /summarize_note
Summarize a medical note using LLM with automatic caching.

**Request (with document_id):**
```json
{
  "document_id": 1
}
```

**Request (with raw text):**
```json
{
  "text": "Patient presents with chest pain, BP 140/90..."
}
```

**Response:**
```json
{
  "summary": "Patient: 45M, presents with chest pain...",
  "cached": false,
  "provider": "openai",
  "model": "gpt-5.1"
}
```

#### POST /query_note
Ask specific questions about a medical note.

**Request:**
```json
{
  "document_id": 2,
  "query": "What medications were prescribed?"
}
```

**Response:**
```json
{
  "answer": "The patient was prescribed Lisinopril 10mg daily...",
  "cached": false,
  "provider": "openai",
  "model": "gpt-5.1"
}
```

**Note:** Both endpoints support `document_id` (preferred) or `text` (fallback). If both are provided, `document_id` takes priority.

### Configuration

**Environment Variables (.env):**
```env
# Database
DATABASE_URL=postgresql://medical_user:medical_pass@localhost:5432/medical_notes

# LLM Provider
LLM_PROVIDER=openai  # or 'anthropic'
LLM_MODEL=gpt-5.1    # or 'claude-sonnet-4-5'
LLM_API_KEY=your_api_key_here
```

**Switching Providers:**
- OpenAI: Set `LLM_PROVIDER=openai` and use your OpenAI API key
- Anthropic: Set `LLM_PROVIDER=anthropic` and use your Anthropic API key

Both providers use the same `LLM_API_KEY` environment variable.

## 📖 API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### Part 1: Backend
- `GET /health` - Health check
- `GET /documents` - List all document IDs
- `POST /documents` - Create new document
- `GET /documents/{id}` - Get document by ID
- `PUT /documents/{id}` - Update document (partial updates supported)
- `DELETE /documents/{id}` - Delete document

#### Part 2: LLM
- `POST /summarize_note` - Summarize medical note
  ```json
  {
    "text": "Medical note content..."
  }
  ```

#### Part 3: RAG
- `POST /answer_question` - Answer question from medical guidelines
  ```json
  {
    "question": "What is the treatment for diabetes?"
  }
  ```

#### Part 4: Agent
- `POST /extract_structured` - Extract structured data from SOAP note
  ```json
  {
    "text": "SOAP note content..."
  }
  ```

#### Part 5: FHIR
- `POST /to_fhir` - Convert structured data to FHIR Bundle
  ```json
  {
    "patient": {...},
    "conditions": [...],
    "medications": [...]
  }
  ```

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🗂️ Project Structure

```
medical_note_processor/
├── src/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # SQLAlchemy setup
│   ├── models.py               # ORM models
│   ├── schemas.py              # Pydantic schemas
│   ├── providers/              # Provider-agnostic LLM & embeddings
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── openai.py
│   │   │   ├── ollama.py
│   │   │   └── factory.py
│   │   └── embeddings/
│   │       ├── base.py
│   │       ├── openai.py
│   │       └── factory.py
│   ├── services/
│   │   └── summarization.py   # Summarization service
│   ├── rag/
│   │   ├── chunking.py         # Document chunking
│   │   ├── vector_store.py     # ChromaDB wrapper
│   │   ├── retriever.py        # Retrieval + reranking
│   │   └── pipeline.py         # RAG orchestration
│   ├── agent/
│   │   ├── schemas.py          # Pydantic models for extraction
│   │   ├── extractors.py       # LLM entity extraction
│   │   ├── api_clients.py      # NIH API clients
│   │   ├── validator.py        # Validation logic
│   │   └── orchestrator.py     # Agent pipeline
│   └── fhir/
│       ├── mappers.py          # FHIR resource mappers
│       └── bundler.py          # FHIR Bundle creator
├── tests/
│   ├── test_part1.py           # Backend tests
│   ├── test_part2.py           # LLM tests
│   ├── test_part3.py           # RAG tests
│   ├── test_part4.py           # Agent tests
│   ├── test_part5.py           # FHIR tests
│   ├── test_part6.py           # Docker tests
│   ├── evaluation/
│   │   ├── test_rag_eval.py    # RAG evaluation
│   │   └── test_agent_eval.py  # Agent evaluation
│   └── golden_sets/
│       ├── rag_qa_pairs.json          # RAG test data
│       └── agent_ground_truth.json    # Agent test data
├── data/
│   ├── soap_notes/             # 6 SOAP notes from assessment
│   │   ├── soap_01.txt
│   │   └── ...
│   └── medical_guidelines/     # RAG knowledge base
│       ├── diabetes_management.md
│       ├── hyperlipidemia_treatment.md
│       └── post_surgical_care.md
├── scripts/
│   ├── seed_database.py        # Seed SOAP notes
│   └── index_documents.py      # Index guidelines for RAG
├── docs/
│   ├── take_home.md                      # Original assessment
│   ├── implementation_plan.md            # Parts 1-3 implementation
│   ├── implementation_plan_parts_4_6.md  # Parts 4-6 implementation
│   └── API_EXAMPLES.md                   # Curl examples
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # Service orchestration
├── Makefile                    # Common commands
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── .dockerignore
└── README.md                   # This file
```

---

## 🛠️ Makefile Commands

```bash
make help      # Show all commands
make build     # Build Docker images
make up        # Start all services
make down      # Stop all services
make logs      # View API logs
make test      # Run all tests
make seed      # Seed database
make index     # Index documents for RAG
make clean     # Remove containers & volumes
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `LLM_PROVIDER` | LLM provider ('openai' or 'ollama') | `openai` |
| `LLM_MODEL` | LLM model name | `gpt-4-turbo` |
| `OPENAI_API_KEY` | OpenAI API key | (required) |
| `EMBEDDING_PROVIDER` | Embedding provider | `openai` |
| `EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `CHUNK_SIZE` | RAG chunk size in tokens | `500` |
| `CHUNK_OVERLAP` | RAG chunk overlap in tokens | `100` |
| `ENABLE_LLM_CACHE` | Enable response caching | `true` |

### Using Ollama (Local LLM)

```bash
# In .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama2

EMBEDDING_PROVIDER=ollama
```

---

## 🏥 Medical Guidelines

Three comprehensive medical guidelines are included for the RAG system:

1. **Diabetes Management** (~1500 words)
   - Type 2 diabetes diagnosis and monitoring
   - Medication protocols (Metformin, GLP-1 agonists, insulin)
   - Lifestyle modifications

2. **Hyperlipidemia Treatment** (~1500 words)
   - Cholesterol screening guidelines
   - Statin therapy protocols
   - Risk stratification

3. **Post-Surgical Care** (~1200 words)
   - Post-operative monitoring
   - Wound care
   - Physical therapy protocols

---

## 📊 Evaluation Criteria

### Correctness & Completeness
- ✅ All 6 parts implemented with stretch goals
- ✅ Direct NIH API integration (ICD-10, RxNorm)
- ✅ Provider-agnostic LLM/embedding architecture
- ✅ RAG with source citations
- ✅ FHIR library usage
- ✅ Comprehensive testing

### Documentation & Setup
- ✅ Single command deployment (`docker-compose up`)
- ✅ Clear README with examples
- ✅ API documentation (Swagger, curl examples)
- ✅ Implementation plan for each part

### Creativity
- ✅ Pydantic Settings for config management
- ✅ Factory pattern for provider abstraction
- ✅ LLM-based reranking in RAG
- ✅ Trajectory logging in agent
- ✅ Custom evaluation frameworks

### Model Agnostic
- ✅ Abstract provider interfaces
- ✅ OpenAI + Ollama support
- ✅ Config-driven model selection
- ✅ Tested with OpenAI (as required for grading)

---

## 🐛 Troubleshooting

### Services won't start
```bash
# Check logs
make logs

# Rebuild
make clean
make build
make up
```

### Database connection issues
```bash
# Check PostgreSQL is healthy
docker-compose ps

# Reset database
make down
docker volume rm medical_note_processor_postgres_data
make up
```

### RAG not returning results
```bash
# Re-index documents
make index

# Check ChromaDB data
docker-compose exec api python -c "from src.rag.vector_store import VectorStore; vs = VectorStore(); print(vs.collection.count())"
```

### API key errors
```bash
# Verify .env file
cat .env | grep OPENAI_API_KEY

# Restart services after changing .env
make down
make up
```

---

## 📝 License

This project is created for a take-home assessment.

---

## 🙏 Acknowledgments

- **SOAP Notes**: Provided in assessment materials
- **NIH APIs**: ICD-10 (ClinicalTables), RxNorm
- **FHIR**: fhir.resources library
- **LLM Providers**: OpenAI, Ollama

---

## 📧 Contact

For questions about this implementation, please refer to the detailed implementation plans in the `docs/` directory.
