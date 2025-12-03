# Medical Note Processor

An AI-powered medical document processing system that extracts structured data from clinical SOAP notes, enriches with ICD-10/RxNorm codes, and outputs FHIR-compliant bundles.

## Quick Start

### 1. Configure


```bash
cp .env.example .env
```


For quick set up: Defaults have been set up for you leveraging OPENAI. Please edit `.env` and add your OpenAI API Key in L13.
```env
LLM_API_KEY=sk-your-LLM-key-here
```
Optional: For further configurability, .env.example allows selection of different language (OpenAI/Anthropic) and embedding (Cohere, OpenAI) model/providers. Read more in [Configuration](#configuration).

### 2. Build & Start

```bash
make build
```

This builds the Docker image, seeds the database with 6 SOAP notes, and indexes medical guidelines for RAG before starting the app. Takes ~2-4 minutes on first run for ingestion pipeline run. See [Commands](#commands) for other options.

### 3. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

**API Documentation:** http://localhost:8000/docs

---

## API Reference

### Part 1: Backend Foundation

Full CRUD API for medical documents built with FastAPI and PostgreSQL.

[View Architecture →](docs/part1-backend.md)

```bash
# List all document IDs
curl http://localhost:8000/documents

# Get a specific document
curl http://localhost:8000/documents/1

# Create a new document
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{"title": "New Note", "content": "Patient presents with...", "doc_type": "soap_note"}'
```

---

### Part 2: LLM Integration

Model-agnostic LLM service with provider abstraction (OpenAI/Anthropic) and response caching.

[View Architecture →](docs/part2-llm.md)

```bash
# Summarize a SOAP note
curl -X POST http://localhost:8000/summarize_note \
  -H "Content-Type: application/json" \
  -d '{"document_id": 1}'

# Ask a question about a specific note
curl -X POST http://localhost:8000/query_note \
  -H "Content-Type: application/json" \
  -d '{"document_id": 2, "query": "What medications were prescribed?"}'
```

---

### Part 3: RAG Pipeline

Question answering over medical guidelines using vector search (FAISS), query reformulation, and source citations.

[View Architecture →](docs/part3-rag.md)

```bash
# Ask a medical question (answered from indexed guidelines)
curl -X POST http://localhost:8000/answer_question \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the target LDL for diabetic patients?"}'
```

**Response includes:** Answer with inline citations `[1]`, source documents, and confidence score.

---

### Part 4: Structured Data Extraction

Agent-based system (with Caching) that extracts patient data, conditions, medications, vitals, labs, and care plans from SOAP notes. Enriches with ICD-10 and RxNorm codes via NIH APIs.

[View Architecture →](docs/part4-agent.md)

```bash
# Extract structured data from a SOAP note
curl -X POST http://localhost:8000/extract_structured \
  -H "Content-Type: application/json" \
  -d '{"document_id": 2}'
```

**Response includes:** Patient info, conditions with ICD-10 codes, medications with RxNorm codes, vital signs, lab results, procedures, and care plan activities.

---

### Part 5: FHIR Conversion

Converts extracted data to FHIR R5 Bundle containing Patient, Condition, MedicationRequest, Observation, Procedure, and CarePlan resources. Includes Caching.

[View Architecture →](docs/part5-fhir.md)

```bash
# Convert to FHIR Bundle (by document_id)
curl -X POST http://localhost:8000/to_fhir \
  -H "Content-Type: application/json" \
  -d '{"document_id": 2}'

# Or by extracted_note_id (from Part 4 response)
curl -X POST http://localhost:8000/to_fhir \
  -H "Content-Type: application/json" \
  -d '{"extracted_note_id": 1}'
```

**Response:** FHIR Bundle with all resources and medical codes preserved.

---

### Part 6: Docker Deployment

Production-ready containerization with multi-stage builds, PostgreSQL, persistent volumes, and smart initialization.

[View Architecture →](docs/part6-docker.md)

---

## Testing

```bash
make test           # All tests (90 tests)
make test-part1     # Backend tests (8)
make test-part2     # LLM tests (8)
make test-part3     # RAG tests (5)
make test-part4     # Agent tests (36)
make test-part5     # FHIR tests (33)
```

---

## Commands

| Command | Description |
|---------|-------------|
| `make build` | Build and initialize (skips if already done) |
| `make rebuild` | Force fresh initialization |
| `make run` | Start without rebuilding |
| `make stop` | Stop all services |
| `make logs` | View application logs |
| `make clean` | Remove all data and containers |

---

## Configuration

### Using different models Instead of OpenAI

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_API_KEY=sk-ant-your-key

# Embeddings can use OpenAI or cohere
EMBEDDING_PROVIDER=cohere
EMBEDDING_API_KEY=sk-your-openai-key
```

### All Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEY` | Yes | - | OpenAI or Anthropic API key |
| `LLM_MODEL` | Yes | - | Model name (e.g., `gpt-4.1`) |
| `LLM_PROVIDER` | Yes | `openai` | `openai` or `anthropic` |
| `EMBEDDING_PROVIDER` | No | `openai` | `openai` or `cohore` |
| `EMBEDDING_API_KEY` | No | `LLM_API_KEY` | Separate key for embeddings |

---

## Project Structure

```
medical_note_processor/
├── src/
│   ├── main.py              # FastAPI endpoints
│   ├── providers/           # LLM & Embedding providers
│   ├── rag/                 # RAG pipeline (FAISS, chunker)
│   ├── agent/               # Extraction agent + NIH APIs
│   └── fhir/                # FHIR R5 conversion
├── data/
│   ├── soap_notes/          # 6 sample SOAP notes
│   └── medical_guidelines/  # RAG knowledge base
├── tests/                   # Test suites by part
├── docs/                    # Architecture documentation
├── Dockerfile               # Multi-stage build
└── docker-compose.yml       # Container orchestration
```

---

## Documentation

| Part | Description | Link |
|------|-------------|------|
| 1 | FastAPI Backend | [docs/part1-backend.md](docs/part1-backend.md) |
| 2 | LLM Integration | [docs/part2-llm.md](docs/part2-llm.md) |
| 3 | RAG Pipeline | [docs/part3-rag.md](docs/part3-rag.md) |
| 4 | Agent Extraction | [docs/part4-agent.md](docs/part4-agent.md) |
| 5 | FHIR Conversion | [docs/part5-fhir.md](docs/part5-fhir.md) |
| 6 | Docker Deployment | [docs/part6-docker.md](docs/part6-docker.md) |
