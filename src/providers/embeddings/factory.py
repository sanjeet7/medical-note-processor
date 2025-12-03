"""Factory for creating embedding providers from configuration"""
from .base import EmbeddingProvider
from .openai import OpenAIEmbeddingProvider
from .cohere import CohereEmbeddingProvider
from src.config import settings


class EmbeddingFactory:
    """
    Factory for creating embedding providers from settings.
    
    Supported providers:
    - openai: OpenAI embeddings (text-embedding-3-small, text-embedding-3-large)
    - cohere: Cohere embeddings (embed-english-v3.0, embed-multilingual-v3.0)
    """
    
    @staticmethod
    def create() -> EmbeddingProvider:
        """
        Create embedding provider based on settings.embedding_provider.
        
        Returns:
            Configured embedding provider instance
            
        Raises:
            ValueError: If provider not supported or model not configured
        """
        provider = settings.embedding_provider.lower()
        
        # Use embedding_api_key if set, otherwise fall back to llm_api_key
        api_key = settings.embedding_api_key or settings.llm_api_key
        
        if not settings.embedding_model:
            raise ValueError("EMBEDDING_MODEL not configured. Set it in .env (e.g., 'text-embedding-3-small' for OpenAI)")
        
        if not api_key:
            raise ValueError("No API key for embeddings. Set EMBEDDING_API_KEY or LLM_API_KEY in .env")
        
        if provider == "openai":
            return OpenAIEmbeddingProvider(
                api_key=api_key,
                model=settings.embedding_model
            )
        elif provider == "cohere":
            return CohereEmbeddingProvider(
                api_key=api_key,
                model=settings.embedding_model
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}. Supported: 'openai', 'cohere'")
