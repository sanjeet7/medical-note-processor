from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime
import hashlib

from .database import Base

class Document(Base):
    """Document storage for SOAP notes and medical guidelines"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    doc_type = Column(String(50), default="general")  # 'soap_note', 'guideline', 'general'
    doc_metadata = Column(JSON, default=dict)  # patient_id, encounter_date, provider, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class LLMCache(Base):
    """Cache for LLM responses to reduce API costs (for Part 2)"""
    __tablename__ = "llm_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_hash = Column(String(64), unique=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @staticmethod
    def hash_prompt(prompt: str, provider: str, model: str) -> str:
        """Create unique hash for prompt + provider + model"""
        combined = f"{prompt}:{provider}:{model}"
        return hashlib.sha256(combined.encode()).hexdigest()
