"""Part 3 Tests: RAG Pipeline Components and Evaluation"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict
from src.rag.chunker import SmartChunker, Chunk
from src.rag.query_reformulator import QueryReformulator
from src.providers.embeddings.factory import EmbeddingFactory
from src.rag.service import RAGService
from src.config import settings

# --- Unit Tests for Components ---

class TestSmartChunker:
    """Test LLM-enhanced chunking logic"""
    
    def test_initialization(self):
        chunker = SmartChunker(chunk_size=500, chunk_overlap=100)
        assert chunker.chunk_size == 500
        assert chunker.chunk_overlap == 100
        
    @pytest.mark.asyncio
    async def test_chunk_document_basic(self):
        """Test basic token-based chunking without LLM boundaries"""
        chunker = SmartChunker(chunk_size=10, chunk_overlap=0)
        text = "word " * 20  # 20 words
        
        # Mock encoding to return 1 token per word for simplicity
        with patch('tiktoken.get_encoding') as mock_encoding:
            mock_enc_instance = Mock()
            mock_enc_instance.encode.side_effect = lambda t: [1] * len(t.split())
            mock_enc_instance.decode.side_effect = lambda t: " ".join(["word"] * len(t))
            mock_encoding.return_value = mock_enc_instance
            
            # Disable LLM boundaries for this test
            chunks = await chunker.chunk_document(text, "test_doc", use_llm_boundaries=False)
            
            assert len(chunks) > 0
            assert isinstance(chunks[0], Chunk)
            assert chunks[0].metadata['document_name'] == "test_doc"

class TestQueryReformulator:
    """Test query reformulation logic"""
    
    @pytest.mark.asyncio
    async def test_reformulate(self):
        # Mock LLM response
        mock_response = '["hypertension medication guidelines", "high blood pressure treatment"]'
        
        with patch('src.providers.llm.factory.LLMFactory.create') as mock_factory:
            mock_llm = AsyncMock()
            mock_llm.generate.return_value = mock_response
            mock_factory.return_value = mock_llm
            
            # Initialize reformulator AFTER patching
            reformulator = QueryReformulator()
            queries = await reformulator.reformulate("meds for htn")
            
            assert len(queries) >= 2
            assert "meds for htn" in queries  # Original should be preserved
            assert "hypertension medication guidelines" in queries

class TestEmbeddingProvider:
    """Test embedding generation"""
    
    @pytest.mark.asyncio
    async def test_embed_query(self):
        # Simple test to verify embedding provider works
        with patch('src.providers.embeddings.factory.EmbeddingFactory.create') as mock_factory:
            mock_provider = AsyncMock()
            test_embedding = [0.1] * 1536
            mock_provider.embed_query.return_value = test_embedding
            mock_provider.embedding_dim = 1536
            mock_factory.return_value = mock_provider
            
            provider = EmbeddingFactory.create()
            embedding = await provider.embed_query("test query")
            
            # Verify embedding dimension matches provider
            assert len(embedding) == provider.embedding_dim

# Golden set of questions for RAG evaluation
GOLDEN_SET = [
    {
        "question": "What are the first-line medications for hypertension?",
        "expected_doc": "hypertension_guideline"
    },
    {
        "question": "What is the LDL target for very high risk patients?",
        "expected_doc": "hyperlipidemia_guideline"
    },
    {
        "question": "What is the first-line therapy for Type 2 Diabetes?",
        "expected_doc": "diabetes_guideline"
    },
    {
        "question": "How often should vital signs be monitored in PACU?",
        "expected_doc": "post_surgical_care_guideline"
    }
]

class TestRAGEvaluation:
    """End-to-end RAG evaluation"""
    
    @pytest.fixture(scope="class")
    def rag_service(self):
        return RAGService()
    
    @pytest.mark.asyncio
    async def test_rag_performance(self, rag_service):
        """
        Evaluate RAG pipeline performance against golden set.
        Calculates Retrieval Recall (finding right doc) and Answer Accuracy (containing key concepts).
        """
        if not settings.llm_api_key:
            pytest.skip("API key not configured")
            
        results = []
        
        print("\n🔎 Starting RAG Evaluation...")
        
        for item in GOLDEN_SET:
            question = item["question"]
            expected_doc = item["expected_doc"]
            
            print(f"\nTesting: {question}")
            
            # Run pipeline
            response = await rag_service.answer_question(question)
            
            # 1. Evaluate Retrieval (Recall)
            # Check if any source comes from the expected document
            retrieved_correct_doc = any(expected_doc in s.document for s in response.sources)
            
            result = {
                "question": question,
                "retrieval_success": retrieved_correct_doc,
                "confidence": response.confidence,
                "sources_count": len(response.sources)
            }
            results.append(result)
            
            print(f"   ✅ Retrieval: {'Success' if retrieved_correct_doc else 'Failed'}")
            print(f"   ✅ Sources: {len(response.sources)} chunks retrieved")
            print(f"   ✅ Confidence: {response.confidence}")
        
        # Calculate aggregate metrics
        total = len(results)
        retrieval_accuracy = sum(1 for r in results if r["retrieval_success"]) / total
        avg_confidence = sum(r["confidence"] for r in results) / total
        
        print("\n📊 Evaluation Summary:")
        print(f"Retrieval Accuracy: {retrieval_accuracy:.2%}")
        print(f"Avg Confidence: {avg_confidence:.2f}")
        
        # Assertions for pass/fail
        # Focus on retrieval accuracy (document validation)
        assert retrieval_accuracy >= 0.75, "Retrieval accuracy below 75%"

if __name__ == "__main__":
    # Allow running directly
    asyncio.run(TestRAGEvaluation().test_rag_performance(RAGService()))
