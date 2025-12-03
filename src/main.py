from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database
from .config import settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup"""
    models.Base.metadata.create_all(bind=database.engine)
    print("✅ Database tables created")
    yield

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Medical Note Processing System - AI Engineer Take Home",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# PART 1 ENDPOINTS
# ============================================================================

@app.get("/health", response_model=schemas.HealthResponse)
def health_check():
    """
    Health check endpoint - returns {"status": "ok"}
    
    This endpoint verifies the server is running properly.
    """
    return {"status": "ok"}

@app.get("/documents", response_model=List[int])
def get_documents(db: Session = Depends(database.get_db)):
    """
    Fetch all document IDs from database
    
    Returns a list of all document IDs for retrieval or processing.
    """
    documents = db.query(models.Document.id).all()
    return [doc.id for doc in documents]

@app.post("/documents", response_model=schemas.DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    document: schemas.DocumentCreate,
    db: Session = Depends(database.get_db)
):
    """
    Create a new document with validation
    
    Accepts:
    - title: Document title (1-255 characters)
    - content: Document content (minimum 1 character)
    - doc_type: Type of document (e.g., 'soap_note', 'guideline')
    - doc_metadata: Additional metadata as JSON
    
    Returns the created document with ID and timestamp.
    """
    db_document = models.Document(**document.model_dump())
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

@app.get("/documents/{document_id}", response_model=schemas.DocumentResponse)
def get_document(document_id: int, db: Session = Depends(database.get_db)):
    """
    Fetch a specific document by ID
    
    Returns:
    - Document with all fields if found
    - 404 error if document doesn't exist
    """
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.put("/documents/{document_id}", response_model=schemas.DocumentResponse)
def update_document(
    document_id: int,
    document: schemas.DocumentUpdate,
    db: Session = Depends(database.get_db)
):
    """
    Update an existing document (partial update supported)
    
    Updates only the provided fields of the document.
    Returns 404 if document doesn't exist.
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Only update fields that are provided (not None)
    update_data = document.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_document, key, value)
    
    db.commit()
    db.refresh(db_document)
    return db_document

@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(database.get_db)):
    """
    Delete a document by ID
    
    Returns:
    - 204 No Content if successful
    - 404 error if document doesn't exist
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.delete(db_document)
    db.commit()
    return None

from .services.llm_service import LLMService
from .schemas import SummarizeRequest, SummarizeResponse, QueryRequest, QueryResponse

@app.post("/summarize_note", response_model=SummarizeResponse)
async def summarize_note(
    request: SummarizeRequest,
    db: Session = Depends(database.get_db)
):
    """Summarize a medical note using LLM with caching"""
    try:
        # Get text from document_id or use provided text
        if request.document_id:
            document = db.query(models.Document).filter(
                models.Document.id == request.document_id
            ).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            note_text = document.content
        elif request.text:
            note_text = request.text
        else:
            raise HTTPException(status_code=400, detail="Either document_id or text must be provided")
        
        service = LLMService(db)
        result = await service.summarize_note(note_text)
        # Map generic result to specific response schema
        return {
            "summary": result["result"],
            "cached": result["cached"],
            "provider": result["provider"],
            "model": result["model"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM summarization failed: {str(e)}"
        )

@app.post("/query_note", response_model=QueryResponse)
async def query_note(
    request: QueryRequest,
    db: Session = Depends(database.get_db)
):
    """Query a medical note using LLM with caching"""
    try:
        # Get text from document_id or use provided text
        if request.document_id:
            document = db.query(models.Document).filter(
                models.Document.id == request.document_id
            ).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            note_text = document.content
        elif request.text:
            note_text = request.text
        else:
            raise HTTPException(status_code=400, detail="Either document_id or text must be provided")
        
        service = LLMService(db)
        result = await service.query_note(note_text, request.query)
        return {
            "answer": result["result"],
            "cached": result["cached"],
            "provider": result["provider"],
            "model": result["model"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM query failed: {str(e)}"
        )

# ============================================================================
# PART 3 ENDPOINT - RAG Pipeline
# ============================================================================

from .rag.service import RAGService
from .schemas import AnswerQuestionRequest, AnswerQuestionResponse, SourceCitation

@app.post("/answer_question", response_model=AnswerQuestionResponse)
async def answer_question(request: AnswerQuestionRequest):
    """
    Answer medical questions using RAG over medical guidelines.
    
    Pipeline:
    1. Query reformulation for better recall
    2. Hybrid retrieval (vector search + LLM reranking)
    3. Dynamic filtering by relevance threshold (>= 0.7)
    4. Answer generation with inline citations
    5. Confidence assessment
    
    Returns:
    - Answer with inline citation markers [1], [2], etc.
    - List of source citations with document, section, and relevance scores
    - Overall confidence score (0.0-1.0)
    - Number of chunks retrieved
    """
    try:
        rag_service = RAGService()
        rag_answer = await rag_service.answer_question(request.question)
        
        # Convert to response schema
        return AnswerQuestionResponse(
            answer=rag_answer.answer,
            sources=[
                SourceCitation(
                    id=source.id,
                    document=source.document,
                    section=source.section,
                    text=source.text
                )
                for source in rag_answer.sources
            ],
            confidence=rag_answer.confidence,
            retrieved_count=rag_answer.retrieved_count
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG question answering failed: {str(e)}"
        )
