"""OpenAI embedding provider implementation"""
import asyncio
from typing import List
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider with batch processing and automatic retries"""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key
            model: Embedding model name (e.g., 'text-embedding-3-small')
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        # Derive dimension from model name (OpenAI model properties)
        # text-embedding-3-small: 1536, text-embedding-3-large: 3072
        self._embedding_dim = 1536 if "3-small" in model else 3072
    
    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension for this model"""
        return self._embedding_dim
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents with batch processing.
        OpenAI allows up to 2048 texts per request for embedding models.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Process in batches of 100 for efficiency
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.embeddings.create(
                model=self.model,
                input=batch
            )
            # Extract embeddings in order
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            text: Query string to embed
            
        Returns:
            Embedding vector
        """
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "openai"
    
    def get_embedding_dim(self) -> int:
        """Return embedding dimensionality"""
        return self._embedding_dim
