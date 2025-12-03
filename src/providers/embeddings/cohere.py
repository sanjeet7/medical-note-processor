"""Cohere embedding provider implementation"""
import httpx
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import EmbeddingProvider


class CohereEmbeddingProvider(EmbeddingProvider):
    """Cohere embedding provider with batch processing and automatic retries"""
    
    def __init__(self, api_key: str, model: str):
        """
        Initialize Cohere embedding provider.
        
        Args:
            api_key: Cohere API key
            model: Embedding model name (e.g., 'embed-english-v3.0')
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.cohere.ai/v1"
        # Cohere embed-english-v3.0 produces 1024-dimensional embeddings
        self._embedding_dim = 1024
    
    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension for this model"""
        return self._embedding_dim
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents with batch processing.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Process in batches of 96 (Cohere's limit)
        batch_size = 96
        all_embeddings = []
        
        async with httpx.AsyncClient() as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = await client.post(
                    f"{self.base_url}/embed",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "texts": batch,
                        "model": self.model,
                        "input_type": "search_document",
                        "truncate": "END"
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                all_embeddings.extend(data["embeddings"])
        
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embed",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "texts": [text],
                    "model": self.model,
                    "input_type": "search_query",
                    "truncate": "END"
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return data["embeddings"][0]
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "cohere"
    
    def get_embedding_dim(self) -> int:
        """Return embedding dimensionality"""
        return self._embedding_dim

