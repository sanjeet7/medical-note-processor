"""Abstract base class for embedding providers"""
from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract interface for embedding generation"""
    
    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of document texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (each is a list of floats)
        """
        pass
    
    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        Args:
            text: Query string to embed
            
        Returns:
            Embedding vector (list of floats)
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider identifier"""
        pass
    
    @abstractmethod
    def get_embedding_dim(self) -> int:
        """Return the dimensionality of embeddings"""
        pass
