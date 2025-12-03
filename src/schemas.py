from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List

# Health check schema
class HealthResponse(BaseModel):
    """Health check response"""
    status: str

# Document schemas
class DocumentBase(BaseModel):
    """Base schema for document with validation"""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    doc_type: str = "general"
    doc_metadata: Dict = Field(default_factory=dict)

class DocumentCreate(DocumentBase):
    """Schema for creating a new document"""
    pass

class DocumentUpdate(BaseModel):
    """Schema for updating a document (all fields optional)"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    doc_type: Optional[str] = None
    doc_metadata: Optional[Dict] = None

class DocumentResponse(DocumentBase):
    """Schema for document response with all fields"""
    id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}

# Summarization schemas (for Part 2)
class SummarizeRequest(BaseModel):
    """Request schema for note summarization"""
    document_id: Optional[int] = None
    text: Optional[str] = Field(None, min_length=1)
    
    @classmethod
    def validate_input(cls, values):
        if not values.get('document_id') and not values.get('text'):
            raise ValueError("Either document_id or text must be provided")
        return values

class SummarizeResponse(BaseModel):
    """Response schema for note summarization"""
    summary: str
    cached: bool
    provider: str
    model: str

# Query schemas
class QueryRequest(BaseModel):
    """Request schema for note querying"""
    document_id: Optional[int] = None
    text: Optional[str] = Field(None, min_length=1)
    query: str = Field(..., min_length=1)
    
    @classmethod
    def validate_input(cls, values):
        if not values.get('document_id') and not values.get('text'):
            raise ValueError("Either document_id or text must be provided")
        return values

class QueryResponse(BaseModel):
    """Response schema for note querying"""
    answer: str
    cached: bool
    provider: str
    model: str

class QueryNoteRequest(BaseModel):
    document_id: int = Field(..., description="ID of document to query")
    query: str = Field(..., min_length=1, max_length=1000, description="Question about the document")


class QueryNoteResponse(BaseModel):
    answer: str
    document_id: int
    document_title: str
    cached: bool
    provider: str
    model: str


# RAG Schemas (Part 3)
class AnswerQuestionRequest(BaseModel):
    """Request for answering questions using RAG over medical guidelines"""
    question: str = Field(..., min_length=1, max_length=2000, description="Medical question")


class SourceCitation(BaseModel):
    """Citation to source document chunk"""
    id: int = Field(..., description="Citation number")
    document: str = Field(..., description="Source document name")
    section: str = Field(..., description="Section title from document")
    text: str = Field(..., description="Relevant excerpt from document")


class AnswerQuestionResponse(BaseModel):
    """Response with answer, citations, and confidence"""
    answer: str = Field(..., description="Answer to question with inline citations")
    sources: List[SourceCitation] = Field(..., description="Source citations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in answer")
    retrieved_count: int = Field(..., description="Number of chunks retrieved")
