"""Hybrid retrieval system with dynamic LLM reranking"""
from typing import List, Dict
from dataclasses import dataclass
import json
from src.rag.vector_store import FAISSVectorStore, SearchResult
from src.rag.query_reformulator import QueryReformulator
from src.providers.embeddings.factory import EmbeddingFactory
from src.providers.llm.factory import LLMFactory
from src.config import settings


@dataclass
class RetrievedChunk:
    """Chunk with relevance status"""
    text: str
    document_name: str
    section: str
    chunk_index: int
    vector_similarity: float  # From vector search (0.0-1.0)


class HybridRetriever:
    """Advanced retrieval with vector search + LLM boolean filtering + query reformulation"""
    
    def __init__(self):
        """Initialize retriever with vector store, embeddings, and LLM"""
        self.vector_store = FAISSVectorStore()
        self.embedding_provider = EmbeddingFactory.create()
        self.llm = LLMFactory.create()
        self.query_reformulator = QueryReformulator()
    
    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        use_reformulation: bool = True
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks using hybrid approach:
        1. Query reformulation (multi-query expansion)
        2. Vector search for each query variant
        3. Result fusion and deduplication
        4. LLM boolean filtering (Relevant/Not Relevant)
        
        Args:
            query: User question
            top_k: Number of chunks for vector search (default: from config)
            use_reformulation: Whether to use query reformulation
            
        Returns:
            List of RetrievedChunk objects that are deemed relevant by LLM
        """
        if top_k is None:
            top_k = settings.retrieval_top_k
        
        # Step 1: Query reformulation
        if use_reformulation:
            queries = await self.query_reformulator.reformulate(query, num_variations=2)
        else:
            queries = [query]
        
        # Step 2: Vector search for all query variants
        all_results = {}  # doc_name_chunk_index -> SearchResult (deduplicated)
        
        for q in queries:
            query_embedding = await self.embedding_provider.embed_query(q)
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                similarity_threshold=settings.similarity_threshold
            )
            
            # Merge results (keep highest similarity if duplicate)
            for result in results:
                key = f"{result.metadata['document_name']}_chunk_{result.metadata['chunk_index']}"
                if key not in all_results or result.similarity_score > all_results[key].similarity_score:
                    all_results[key] = result
        
        # Step 3: Get top-k by vector similarity
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x.similarity_score,
            reverse=True
        )[:top_k]
        
        if not sorted_results:
            return []
        
        # Step 4: LLM boolean filtering
        relevant_chunks = await self._filter_with_llm(query, sorted_results)
        
        return relevant_chunks
    
    async def _filter_with_llm(
        self,
        query: str,
        search_results: List[SearchResult]
    ) -> List[RetrievedChunk]:
        """
        Filter search results using LLM boolean decision.
        
        Args:
            query: Original user query
            search_results: Results from vector search
            
        Returns:
            List of RetrievedChunk objects deemed relevant
        """
        relevant_chunks = []
        
        for result in search_results:
            # Get boolean relevance from LLM
            is_relevant = await self._check_relevance(query, result.chunk_text)
            
            if is_relevant:
                relevant_chunks.append(RetrievedChunk(
                    text=result.chunk_text,
                    document_name=result.metadata['document_name'],
                    section=result.metadata.get('section_title', 'Unknown'),
                    chunk_index=result.metadata['chunk_index'],
                    vector_similarity=result.similarity_score
                ))
        
        return relevant_chunks
    
    async def _check_relevance(self, query: str, chunk_text: str) -> bool:
        """
        Check relevance of chunk to query using LLM (Boolean decision).
        
        Args:
            query: User question
            chunk_text: Chunk text to check
            
        Returns:
            True if relevant, False otherwise
        """
        prompt = f"""Determine if this medical guideline chunk is relevant to answering the question.
        
Question: {query}

Chunk: {chunk_text[:1000]}...

Is this chunk relevant? (Yes/No)
Return ONLY a JSON object:
{{
  "relevant": <bool>,
  "reasoning": "<brief explanation>"
}}

JSON:"""
        
        try:
            response = await self.llm.generate(prompt)
            result = json.loads(response.strip())
            return bool(result.get('relevant', False))
        except Exception as e:
            # Fallback: assume relevant if LLM fails (fail open)
            print(f"LLM relevance check failed: {e}")
            return True
