from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import hashlib

from .database import Base


def utcnow():
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class Document(Base):
    """Document storage for SOAP notes and medical guidelines"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    doc_type = Column(String(50), default="general")  # 'soap_note', 'guideline', 'general'
    doc_metadata = Column(JSON, default=dict)  # patient_id, encounter_date, provider, etc.
    created_at = Column(DateTime, default=utcnow)
    
    # Relationship to extracted notes
    extracted_notes = relationship("ExtractedNote", back_populates="document")


class ExtractedNote(Base):
    """
    Storage for structured data extracted from SOAP notes (Part 4).
    
    Links to the source document if extraction was from document_id.
    Stores the full StructuredNote JSON for FHIR conversion in Part 5.
    Also caches FHIR Bundle output to avoid re-conversion.
    """
    __tablename__ = "extracted_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    structured_data = Column(JSON, nullable=False)  # Full StructuredNote as JSON
    entity_counts = Column(JSON, default=dict)  # Summary counts
    fhir_bundle = Column(JSON, nullable=True)  # Cached FHIR Bundle output
    created_at = Column(DateTime, default=utcnow)
    
    # Relationship to source document
    document = relationship("Document", back_populates="extracted_notes")

class LLMCache(Base):
    """Cache for LLM responses to reduce API costs (for Part 2)"""
    __tablename__ = "llm_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_hash = Column(String(64), unique=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow)
    
    @staticmethod
    def hash_prompt(prompt: str, provider: str, model: str) -> str:
        """Create unique hash for prompt + provider + model"""
        combined = f"{prompt}:{provider}:{model}"
        return hashlib.sha256(combined.encode()).hexdigest()
