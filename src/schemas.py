from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict

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
    text: str = Field(..., min_length=1)

class SummarizeResponse(BaseModel):
    """Response schema for note summarization"""
    summary: str
    cached: bool
    provider: str
    model: str
