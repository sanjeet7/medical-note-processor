"""FAISS vector store for medical guidelines"""
import faiss
import numpy as np
import pickle
import json
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
from src.rag.chunker import Chunk
from src.config import settings


@dataclass
class SearchResult:
    """Represents a search result from vector store"""
    chunk_text: str
    metadata: Dict
    distance: float  # L2 distance
    similarity_score: float  # Converted similarity


class FAISSVectorStore:
    """FAISS-based vector store with metadata persistence"""
    
    def __init__(self, persist_directory: str = None):
        """
        Initialize FAISS vector store.
        
        Args:
            persist_directory: Directory to persist index and metadata
        """
        from src.providers.embeddings.factory import EmbeddingFactory
        
        self.persist_directory = persist_directory or settings.faiss_db_path
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Get embedding dimension from provider (model property)
        embedding_provider = EmbeddingFactory.create()
        self.dimension = embedding_provider.embedding_dim
        
        self.index_path = Path(self.persist_directory) / "index.faiss"
        self.metadata_path = Path(self.persist_directory) / "metadata.pkl"
        
        self.index = None
        self.metadata_store = {}  # int_id -> dict
        
        self._load()
    
    def _load(self):
        """Load index and metadata from disk if they exist"""
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, "rb") as f:
                    self.metadata_store = pickle.load(f)
            except Exception as e:
                print(f"Error loading FAISS index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()
            
    def _create_new_index(self):
        """Create a new FAISS index"""
        # Using IndexFlatL2 for exact search (sufficient for this scale)
        # For larger datasets, could use IndexIVFFlat
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata_store = {}
    
    def _save(self):
        """Save index and metadata to disk"""
        if self.index:
            faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata_store, f)
            
    def add_documents(
        self,
        chunks: List[Chunk],
        embeddings: List[List[float]],
        doc_name: str
    ):
        """
        Add document chunks with embeddings to vector store.
        
        Args:
            chunks: List of Chunk objects
            embeddings: List of embedding vectors
            doc_name: Document name for metadata
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        
        if not chunks:
            return
            
        # Convert embeddings to numpy array (float32 required by FAISS)
        vectors = np.array(embeddings).astype('float32')
        
        # Add to index
        start_id = self.index.ntotal
        self.index.add(vectors)
        
        # Store metadata
        for i, chunk in enumerate(chunks):
            global_id = start_id + i
            metadata = {
                'text': chunk.text,
                'document_name': doc_name,
                'chunk_index': chunk.chunk_index,
                'total_chunks': chunk.metadata.get('total_chunks', 0),
                'section_title': chunk.metadata.get('section_title', 'Unknown'),
                'key_concepts': chunk.metadata.get('key_concepts', [])
            }
            self.metadata_store[global_id] = metadata
            
        # Persist changes
        self._save()
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: float = 0.5
    ) -> List[SearchResult]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results
            similarity_threshold: Minimum similarity (0-1)
            
        Returns:
            List of SearchResult objects
        """
        if self.index is None or self.index.ntotal == 0:
            return []
            
        # Prepare query vector
        query_vector = np.array([query_embedding]).astype('float32')
        
        # Search
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for i in range(len(indices[0])):
            idx = int(indices[0][i])
            dist = float(distances[0][i])
            
            if idx == -1:  # No result found
                continue
                
            # Convert L2 distance to similarity
            # For normalized vectors, L2 = 2(1-cos). So cos = 1 - L2/2
            # Assuming embeddings are normalized (OpenAI's usually are)
            similarity = max(0.0, 1.0 - (dist / 2.0))
            
            if similarity >= similarity_threshold:
                metadata = self.metadata_store.get(idx, {})
                results.append(SearchResult(
                    chunk_text=metadata.get('text', ''),
                    metadata=metadata,
                    distance=dist,
                    similarity_score=similarity
                ))
                
        return results
    
    def delete_collection(self):
        """Delete/Reset the collection"""
        self._create_new_index()
        self._save()
        
    def get_collection_count(self) -> int:
        """Get number of vectors in index"""
        return self.index.ntotal if self.index else 0
