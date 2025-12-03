# Part 6: Docker Containerization

Production-ready Docker deployment with multi-stage builds, PostgreSQL, persistent volumes, and automatic initialization.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      docker-compose.yml                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    api (FastAPI)                         │   │
│   │                                                          │   │
│   │   Port: 8000                                             │   │
│   │   Image: python:3.12-slim (multi-stage)                 │   │
│   │                                                          │   │
│   │   Environment:                                           │   │
│   │   ├── DATABASE_URL                                      │   │
│   │   ├── LLM_API_KEY       ◀── from .env                   │   │
│   │   ├── LLM_PROVIDER                                      │   │
│   │   ├── EMBEDDING_API_KEY                                 │   │
│   │   └── FORCE_INIT                                        │   │
│   │                                                          │   │
│   │   Volumes:                                               │   │
│   │   ├── faiss_data:/app/data/faiss_db  (persistent)       │   │
│   │   ├── ./src:/app/src:ro              (hot-reload)       │   │
│   │   └── ./scripts:/app/scripts:ro                         │   │
│   │                                                          │   │
│   │   Health: http://localhost:8000/health                  │   │
│   └──────────────────────────┬──────────────────────────────┘   │
│                              │                                   │
│                              │ depends_on                        │
│                              │ (service_healthy)                 │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                 postgres (PostgreSQL 15)                 │   │
│   │                                                          │   │
│   │   Port: 5432                                             │   │
│   │   User: medical_user                                     │   │
│   │   Database: medical_notes                                │   │
│   │                                                          │   │
│   │   Volume:                                                │   │
│   │   └── postgres_data:/var/lib/postgresql/data            │   │
│   │                                                          │   │
│   │   Health: pg_isready                                     │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│   Volumes:                                                       │
│   ├── postgres_data    (named: medical_notes_postgres_data)     │
│   └── faiss_data       (named: medical_notes_faiss_data)        │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-Stage Dockerfile

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: builder                                                │
│                                                                  │
│  FROM python:3.12-slim                                          │
│  ├── Install build-essential, libpq-dev                         │
│  ├── Copy requirements.txt                                      │
│  └── pip install --user (to ~/.local)                           │
├─────────────────────────────────────────────────────────────────┤
│  Stage 2: runtime                                                │
│                                                                  │
│  FROM python:3.12-slim                                          │
│  ├── Install libpq5, postgresql-client only                     │
│  ├── Create non-root user (appuser)                             │
│  ├── COPY --from=builder ~/.local packages                      │
│  ├── Copy application code                                      │
│  ├── HEALTHCHECK via /health endpoint                           │
│  └── ENTRYPOINT scripts/entrypoint.sh                           │
└─────────────────────────────────────────────────────────────────┘

Benefits:
• Smaller image (~400MB vs ~1GB)
• No build tools in production
• Non-root user for security
```

## Smart Initialization

The `entrypoint.sh` script handles automatic setup:

```
┌─────────────────────────────────────────────────────────────────┐
│                    entrypoint.sh Flow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. Wait for PostgreSQL                                         │
│      └── pg_isready (max 30 attempts)                           │
│                                                                  │
│   2. Database Seeding                                            │
│      ├── Check: SELECT COUNT(*) FROM documents                  │
│      ├── If empty OR FORCE_INIT=true:                           │
│      │   └── Run: python scripts/seed_database.py               │
│      └── Else: Skip (already seeded)                            │
│                                                                  │
│   3. FAISS Indexing                                              │
│      ├── Check: /app/data/faiss_db/index.faiss exists?          │
│      ├── If missing OR FORCE_INIT=true:                         │
│      │   └── Run: python scripts/index_guidelines.py            │
│      └── Else: Skip (already indexed)                           │
│                                                                  │
│   4. Start Server                                                │
│      └── uvicorn src.main:app --host 0.0.0.0 --port 8000       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Environment Configuration

Create `.env` from template:

```bash
cp .env.example .env
```

**Required Variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | OpenAI or Anthropic API key | `sk-...` |
| `LLM_MODEL` | Model name | `gpt-4.1` |

**Optional Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | `openai` or `anthropic` |
| `EMBEDDING_PROVIDER` | `openai` | Embedding provider |
| `EMBEDDING_MODEL` | - | Embedding model name |
| `EMBEDDING_API_KEY` | `LLM_API_KEY` | Separate key for embeddings |
| `FORCE_INIT` | `false` | Force re-seed and re-index |

## Persistence

Both PostgreSQL data and FAISS index survive container restarts:

```yaml
volumes:
  postgres_data:
    name: medical_notes_postgres_data   # Database tables
  faiss_data:
    name: medical_notes_faiss_data      # Vector index
```

## Commands

### Quick Start

```bash
# 1. Configure
cp .env.example .env
# Edit .env with your LLM_API_KEY

# 2. Build and start (smart init)
make build
# Or: docker-compose up --build -d

# 3. Verify
curl http://localhost:8000/health
```

### Development

```bash
make run      # Start (quick, no build)
make stop     # Stop services
make logs     # View logs
make rebuild  # Force re-initialization
make clean    # Remove all data
```

### Force Re-initialization

```bash
# Re-seed database and re-index guidelines
FORCE_INIT=true docker-compose up -d

# Or via Makefile
make rebuild
```

## Health Checks

Both services have health checks:

**PostgreSQL:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U medical_user -d medical_notes"]
  interval: 5s
  timeout: 5s
  retries: 5
```

**API:**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
  interval: 30s
  timeout: 10s
  start_period: 30s
  retries: 3
```

## Key Design Decisions

### 1. Multi-Stage Build
Separates build dependencies from runtime, resulting in:
- Smaller production image
- Faster deployments
- Better security

### 2. Smart Initialization
Avoids redundant work on restarts:
- Checks if DB already seeded
- Checks if FAISS index exists
- `FORCE_INIT=true` overrides for testing

### 3. Non-Root User
Container runs as `appuser` (not root) for security best practices.

### 4. Volume Mounts for Development
Source code mounted read-only enables hot-reloading during development:
```yaml
volumes:
  - ./src:/app/src:ro
  - ./scripts:/app/scripts:ro
```

### 5. Service Dependencies
API waits for PostgreSQL health before starting:
```yaml
depends_on:
  postgres:
    condition: service_healthy
```

