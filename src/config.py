from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration with environment variable support"""
    
    # Database
    database_url: str = "postgresql://medical_user:medical_pass@localhost:5432/medical_notes"
    
    # App
    app_name: str = "Medical Note Processor"
    debug: bool = False
    
    # LLM Configuration (REQUIRED - set in .env)
    llm_provider: str = "openai"  # 'openai' or 'anthropic'
    llm_model: str = ""  # Required: e.g., 'gpt-4' for OpenAI, 'claude-3-opus-20240229' for Anthropic
    llm_api_key: str = ""  # Required: OpenAI or Anthropic API key
    
    # Embedding Configuration (for Part 3)
    # Note: Embeddings currently only support OpenAI
    embedding_provider: str = "openai"
    embedding_model: str = ""  # Required: e.g., 'text-embedding-3-small'
    embedding_api_key: str = ""  # Optional: defaults to llm_api_key if empty
    
    # RAG Configuration (for Part 3)
    chunk_size: int = 500
    chunk_overlap: int = 100
    retrieval_top_k: int = 10
    similarity_threshold: float = 0.3  # Minimum cosine similarity for vector search
    faiss_db_path: str = "data/faiss_db"
    
    # Metadata LLM (optional - for cost-effective metadata extraction)
    # If empty, falls back to llm_model
    metadata_llm_model: str = ""  # e.g., 'gpt-4o-mini' for cheaper operations
    
    # Cache
    enable_llm_cache: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
