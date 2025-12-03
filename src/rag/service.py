"""RAG service for medical question answering"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from src.rag.retriever import HybridRetriever, RetrievedChunk
from src.providers.llm.factory import LLMFactory


@dataclass
class Citation:
    """Source citation for answer"""
    id: int
    document: str
    section: str
    text: str


@dataclass
class RAGAnswer:
    """Answer with sources and confidence"""
    answer: str
    sources: List[Citation]
    confidence: float
    retrieved_count: int


class RAGService:
    """High-level RAG orchestration for medical Q&A"""
    
    def __init__(self):
        """Initialize RAG service"""
        self.retriever = HybridRetriever()
        self.llm = LLMFactory.create()
    
    async def answer_question(
        self,
        question: str,
        min_confidence: float = 0.3
    ) -> RAGAnswer:
        """
        Answer medical question using RAG pipeline.
        
        Pipeline:
        1. Retrieve relevant chunks (with query reformulation + boolean filtering)
        2. Assemble context with citations
        3. Generate answer using LLM
        4. Assess confidence
        
        Args:
            question: User's medical question
            min_confidence: Minimum confidence for definitive answer
            
        Returns:
            RAGAnswer with answer text, citations, and confidence score
        """
        # Step 1: Retrieve relevant chunks
        retrieved_chunks = await self.retriever.retrieve(
            query=question,
            use_reformulation=True
        )
        
        if not retrieved_chunks:
            return RAGAnswer(
                answer="I don't have enough information in the medical guidelines to answer this question.",
                sources=[],
                confidence=0.0,
                retrieved_count=0
            )
        
        # Step 2: Build context with citation markers
        context_parts = []
        citations = []
        
        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_parts.append(f"[{i}] {chunk.text}\n")
            citations.append(Citation(
                id=i,
                document=chunk.document_name,
                section=chunk.section,
                text=chunk.text
            ))
        
        context = "\n".join(context_parts)
        
        # Step 3: Generate answer with LLM
        answer_text = await self._generate_answer(question, context)
        
        # Step 4: Assess confidence
        confidence = await self._assess_confidence(
            question=question,
            answer=answer_text,
            retrieved_chunks=retrieved_chunks
        )
        
        # If very low confidence, return disclaimer
        if confidence < min_confidence:
            answer_text = f"Based on the available guidelines, {answer_text}\n\n" \
                         f"Note: Limited information available (confidence: {confidence:.2f}). " \
                         f"Please consult comprehensive medical resources or a healthcare professional."
        
        return RAGAnswer(
            answer=answer_text,
            sources=citations,
            confidence=confidence,
            retrieved_count=len(retrieved_chunks)
        )
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """
        Generate answer using LLM with retrieved context.
        
        Args:
            question: User question
            context: Retrieved context with citation markers
            
        Returns:
            Answer text with inline citations
        """
        prompt = f"""You are a medical information assistant. Answer the question based ONLY on the provided medical guideline excerpts.

CRITICAL GUARDRAILS:
1. Use ONLY information explicitly stated in the provided sources
2. Do NOT make inferences, extrapolations, or use external knowledge
3. If the sources don't contain enough information to answer fully, you MUST say: "I don't have enough information in the provided guidelines to answer this question completely."
4. Cite every claim with inline markers [1], [2], etc.
5. Do NOT hallucinate or invent information not present in the sources
6. Be specific and cite relevant details from the guidelines
7. If uncertain about any part, acknowledge the limitation

Medical Guideline Excerpts:
{context}

Question: {question}

Answer (with citations):"""
        
        answer = await self.llm.generate(prompt)
        return answer.strip()
    
    async def _assess_confidence(
        self,
        question: str,
        answer: str,
        retrieved_chunks: List[RetrievedChunk]
    ) -> float:
        """
        Assess confidence in the answer using LLM evaluation.
        
        Args:
            question: Original question
            answer: Generated answer
            retrieved_chunks: Chunks used for answer
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if not retrieved_chunks:
            return 0.0
        
        # Use LLM to evaluate answer quality
        prompt = f"""Evaluate the quality and completeness of this medical answer.

Question: {question}

Answer: {answer}

Number of sources used: {len(retrieved_chunks)}

Rate confidence (0.0-1.0) based on:
1. Completeness: Does the answer fully address the question?
2. Source support: Is the answer well-supported by the sources?
3. Clarity: Is the answer clear and specific?
4. Appropriateness: Does it acknowledge limitations if information is incomplete?

Return ONLY a JSON object:
{{
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<brief explanation>"
}}

JSON:"""
        
        try:
            response = await self.llm.generate(prompt)
            result = json.loads(response.strip())
            confidence = float(result.get('confidence', 0.5))
            # Clamp to [0, 1]
            return max(0.0, min(1.0, confidence))
        except Exception as e:
            # Fallback to simple heuristic if LLM fails
            print(f"LLM confidence assessment failed: {e}")
            # Simple fallback: based on chunk count
            return min(1.0, len(retrieved_chunks) / 3.0)
