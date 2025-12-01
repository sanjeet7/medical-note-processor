from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration with environment variable support"""
    
    # Database
    database_url: str = "postgresql://medical_user:medical_pass@localhost:5432/medical_notes"
    
    # App
    app_name: str = "Medical Note Processor"
    debug: bool = False
    
    # LLM Configuration (for Part 2)
    llm_provider: str = "openai"  # 'openai' or 'ollama'
    llm_model: str = "gpt-5"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    
    # Embedding Configuration (for Part 3)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    
    # RAG Configuration (for Part 3)
    chunk_size: int = 500
    chunk_overlap: int = 100
    retrieval_top_k: int = 10
    rerank_top_k: int = 3
    
    # Cache
    enable_llm_cache: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
