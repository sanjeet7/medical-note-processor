# Medical Note Processing System

> **AI Engineer Take-Home Assessment** - Healthcare document processing with LLM, RAG, and FHIR

A production-grade medical note processing system with FastAPI, RAG pipeline, agent-based extraction with NIH API integration, and FHIR conversion.

---

## 🎯 Overview

This system automates medical document processing workflows:
- **FastAPI backend** with PostgreSQL database
- **LLM integration** for summarization (provider-agnostic: OpenAI, Anthropic)
- **RAG pipeline** for medical guideline Q&A with citations
- **Agent-based extraction** with NIH API integration (ICD-10, RxNorm)
- **FHIR conversion** using fhir.resources library
- **Docker deployment** with docker-compose

---

## ✨ Features

### Part 1: FastAPI Backend ✅
- Health check endpoint
- Full CRUD operations with validation
- Partial updates support
- Database seeding with 6 SOAP notes

### Part 2: LLM Integration ✅
- OpenAI and Anthropic provider support
- `/summarize_note` - Summarize medical notes
- `/query_note` - Ask questions about notes
- Response caching to reduce API costs

### Part 3: RAG Pipeline ✅
- Medical guidelines knowledge base (4 documents)
- FAISS vector store with persistence
- Query reformulation for better recall
- LLM-based relevance filtering
- Source citations in answers

### Part 4: Agent System ✅
- **ReAct-style orchestrator** with tool-based architecture
- **LLM entity extraction** (patient, conditions, medications, vitals, labs, procedures)
- **ICD-10 code lookup** via NIH ClinicalTables API
- **RxNorm code lookup** via NIH RxNav API
- **Trajectory logging** for debugging/audit
- **FHIR-aligned models** for Part 5 compatibility
- **36 tests** (unit + integration + golden set)

### Part 5: FHIR Conversion 🔴
- FHIR resource mapping (Patient, Condition, MedicationRequest, Observation)
- FHIR Bundle creation
- Spec-compliant using fhir.resources library

### Part 6: Containerization 🔴
- Multi-stage Dockerfile
- Docker Compose orchestration
- Auto-seeding and indexing

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL (or Docker)
- OpenAI API key

### Setup

```bash
# 1. Create virtual environment
make setup

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY (LLM_API_KEY)

# 3. Start PostgreSQL
make db-up

# 4. Seed database and index guidelines
make seed
make index-guidelines

# 5. Run the application
make run
```

### Verify Installation

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# List documents
curl http://localhost:8000/documents
# Expected: [1, 2, 3, 4, 5, 6]
```

---

## 📖 API Endpoints

### Part 1: Backend
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/documents` | List all document IDs |
| POST | `/documents` | Create document |
| GET | `/documents/{id}` | Get document |
| PUT | `/documents/{id}` | Update document |
| DELETE | `/documents/{id}` | Delete document |

### Part 2: LLM
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/summarize_note` | Summarize medical note |
| POST | `/query_note` | Query medical note |

### Part 3: RAG
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/answer_question` | Answer from guidelines |

### Part 4: Agent
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/extract_structured` | Extract structured data |

---

## 🔬 Part 4: Agent System Details

### Architecture

```
ExtractionAgent (Orchestrator)
├── Step 1: EntityExtractionTool (LLM)
│   └── Extracts raw entities from SOAP note
├── Step 2: ICD10LookupTool (NIH API) [parallel]
│   └── Enriches conditions with ICD-10 codes
├── Step 3: RxNormLookupTool (NIH API) [parallel]
│   └── Enriches medications with RxNorm codes
├── Step 4: Transform
│   └── Convert to FHIR-aligned models
└── Step 5: ValidationTool (Pydantic)
    └── Validate final output
```

### Example Request

```bash
curl -X POST http://localhost:8000/extract_structured \
  -H "Content-Type: application/json" \
  -d '{"document_id": 2}'
```

### Example Response

```json
{
  "success": true,
  "structured_data": {
    "patient": {
      "identifier": "patient--001",
      "name": null,
      "gender": null
    },
    "encounter": {
      "date": "2024-03-15",
      "type": "follow-up"
    },
    "conditions": [
      {
        "code": {
          "code": "E78.5",
          "system": "http://hl7.org/fhir/sid/icd-10-cm",
          "display": "Hyperlipidemia, unspecified"
        },
        "clinical_status": "active",
        "verification_status": "confirmed"
      }
    ],
    "medications": [
      {
        "code": {
          "code": "83367",
          "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
          "display": "atorvastatin"
        },
        "dosage": {
          "text": "20 mg oral daily",
          "dose_value": 20,
          "dose_unit": "mg",
          "frequency": "daily"
        },
        "status": "active"
      }
    ],
    "vital_signs": [
      {"code": {"display": "Blood Pressure"}, "value": 134, "unit": "mmHg"}
    ],
    "lab_results": [...],
    "care_plan": [...]
  },
  "entity_counts": {
    "conditions": 2,
    "medications": 1,
    "vital_signs": 3,
    "care_plan": 1
  },
  "trajectory": {
    "agent_name": "ExtractionAgent",
    "success": true,
    "total_duration_ms": 2500,
    "steps": [...]
  }
}
```

---

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Test Individual Parts
```bash
make test-part1          # Backend tests
make test-part2          # LLM tests
make test-part3          # RAG tests
make test-part4          # Agent tests (36 tests)
make test-part4-unit     # Agent unit tests (fast, mocked)
make test-part4-api      # Real NIH API tests
make test-part4-golden   # Golden set evaluation
```

### Part 4 Test Results

```
📊 Real NIH API Results:
✅ ICD-10 for 'Hyperlipidemia': E78.2 - Mixed hyperlipidemia
✅ ICD-10 for 'Essential Hypertension': I10 - Essential (primary) hypertension
✅ ICD-10 for 'Type 2 Diabetes Mellitus': E11.65
✅ RxNorm for 'atorvastatin': RxCUI=83367
✅ RxNorm for 'ibuprofen': RxCUI=5640
✅ RxNorm for 'lisinopril': RxCUI=29046

📊 Golden Set Evaluation:
Success Rate: 2/2
Avg Condition Recall: 100.00%
Avg Medication Recall: 100.00%
```

---

## 🗂️ Project Structure

```
medical_note_processor/
├── src/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Pydantic Settings
│   ├── database.py             # SQLAlchemy setup
│   ├── models.py               # ORM models
│   ├── schemas.py              # API schemas
│   ├── providers/              # LLM & embedding providers
│   │   ├── llm/
│   │   └── embeddings/
│   ├── services/               # Business logic
│   ├── rag/                    # RAG pipeline
│   └── agent/                  # Part 4: Extraction agent
│       ├── models.py           # FHIR-aligned schemas
│       ├── orchestrator.py     # ReAct orchestrator
│       ├── trajectory.py       # Audit logging
│       └── tools/              # Agent tools
│           ├── base.py
│           ├── extractor.py    # LLM extraction
│           ├── icd_lookup.py   # NIH ICD-10 API
│           ├── rxnorm_lookup.py # NIH RxNorm API
│           └── validator.py
├── tests/
│   ├── test_part1.py
│   ├── test_part2.py
│   ├── test_part3.py
│   └── test_part4.py           # 36 tests
├── data/
│   ├── soap_notes/             # 6 SOAP notes
│   └── medical_guidelines/     # RAG knowledge base
├── scripts/
│   ├── seed_database.py
│   └── index_guidelines.py
├── docs/
│   ├── Status.md
│   ├── implementation_plan.md
│   └── implementation_plan_parts_3_6.md
├── Makefile
├── requirements.txt
└── README.md
```

---

## 🛠️ Makefile Commands

```bash
make help                # Show all commands

# Setup
make setup               # Create venv, install deps

# Testing
make test                # Run all tests
make test-unit           # Unit tests only (fast)
make test-integration    # Integration tests (real APIs)
make test-part4          # Part 4 tests
make test-part4-api      # Real NIH API tests

# Database
make db-up               # Start PostgreSQL
make db-down             # Stop PostgreSQL
make seed                # Seed SOAP notes
make index-guidelines    # Index for RAG

# Running
make run                 # Start application
make run-dev             # Development mode

# Cleanup
make clean               # Remove cache files
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://...` |
| `LLM_PROVIDER` | LLM provider | `openai` |
| `LLM_MODEL` | LLM model | `gpt-4` |
| `LLM_API_KEY` | API key | (required) |
| `EMBEDDING_PROVIDER` | Embedding provider | `openai` |
| `EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |

---

## 📊 Evaluation Criteria

| Criteria | Status | Implementation |
|----------|--------|----------------|
| **Correctness** | ✅ | 4/6 parts complete, all tests passing |
| **Documentation** | ✅ | Comprehensive README, Status, plans |
| **Creativity** | ✅ | ReAct pattern, trajectory logging, parallel NIH API calls |
| **Model Agnostic** | ✅ | Abstract providers, OpenAI + Anthropic support |

---

## 📝 License

This project is created for a take-home assessment.

---

## 🙏 Acknowledgments

- **SOAP Notes**: Provided in assessment materials
- **NIH APIs**: ICD-10 (ClinicalTables), RxNorm (RxNav)
- **FHIR**: fhir.resources library
- **LLM Providers**: OpenAI, Anthropic
