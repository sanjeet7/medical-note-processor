#!/bin/bash
# Entrypoint script for Medical Note Processor
# 
# Features:
# - Waits for PostgreSQL to be ready
# - Smart detection: skips seeding/indexing if already done
# - FORCE_INIT=true environment variable to re-run initialization
# - Starts uvicorn server

set -e

echo "=================================================="
echo "Medical Note Processor - Starting Up"
echo "=================================================="

# Configuration
DB_HOST="${DATABASE_URL#*@}"
DB_HOST="${DB_HOST%%/*}"
DB_HOST="${DB_HOST%%:*}"
FORCE_INIT="${FORCE_INIT:-false}"
FAISS_INDEX_PATH="/app/data/faiss_db/index.faiss"

echo "Database Host: $DB_HOST"
echo "Force Init: $FORCE_INIT"

# ============================================================================
# Wait for PostgreSQL
# ============================================================================
echo ""
echo "🔄 Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if pg_isready -h "$DB_HOST" -U medical_user -d medical_notes > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts - waiting..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ PostgreSQL did not become ready in time"
    exit 1
fi

# ============================================================================
# Database Seeding
# ============================================================================
echo ""
echo "🔄 Checking database status..."

# Check if documents table has data
DOC_COUNT=$(python -c "
from src.database import SessionLocal, engine
from src.models import Base, Document
from sqlalchemy import inspect

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Check if documents exist
db = SessionLocal()
try:
    count = db.query(Document).count()
    print(count)
finally:
    db.close()
" 2>/dev/null || echo "0")

echo "   Documents in database: $DOC_COUNT"

if [ "$FORCE_INIT" = "true" ] || [ "$DOC_COUNT" = "0" ]; then
    if [ "$FORCE_INIT" = "true" ]; then
        echo "🔄 FORCE_INIT=true - Running database seeding..."
    else
        echo "🔄 Database empty - Running database seeding..."
    fi
    python scripts/seed_database.py
    echo "✅ Database seeding complete!"
else
    echo "✅ Database already seeded - skipping (use FORCE_INIT=true to re-seed)"
fi

# ============================================================================
# FAISS Index
# ============================================================================
echo ""
echo "🔄 Checking FAISS index status..."

if [ "$FORCE_INIT" = "true" ] || [ ! -f "$FAISS_INDEX_PATH" ]; then
    if [ "$FORCE_INIT" = "true" ]; then
        echo "🔄 FORCE_INIT=true - Rebuilding FAISS index..."
    else
        echo "🔄 FAISS index not found - Building index..."
    fi
    python scripts/index_guidelines.py
    echo "✅ FAISS indexing complete!"
else
    echo "✅ FAISS index exists - skipping (use FORCE_INIT=true to re-index)"
fi

# ============================================================================
# Start Application
# ============================================================================
echo ""
echo "=================================================="
echo "🚀 Starting FastAPI server on port 8000"
echo "=================================================="
echo ""

exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

