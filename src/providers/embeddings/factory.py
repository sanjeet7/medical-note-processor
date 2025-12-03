"""Factory for creating embedding providers from configuration"""
from .base import EmbeddingProvider
from .openai import OpenAIEmbeddingProvider
from src.config import settings


class EmbeddingFactory:
    """Factory for creating embedding providers from settings"""
    
    @staticmethod
    def create() -> EmbeddingProvider:
        """
        Create embedding provider based on settings.embedding_provider.
        
        Returns:
            Configured embedding provider instance
            
        Raises:
            ValueError: If provider not supported
        """
        provider = settings.embedding_provider.lower()
        
        if provider == "openai":
            return OpenAIEmbeddingProvider(
                api_key=settings.llm_api_key,
                model=settings.embedding_model
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
