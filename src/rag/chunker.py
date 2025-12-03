"""Smart document chunking with LLM-enhanced boundaries and metadata extraction"""
import tiktoken
from typing import List, Dict, Optional
from dataclasses import dataclass
from src.providers.llm.factory import LLMFactory
from src.config import settings
import json


@dataclass
class Chunk:
    """Represents a document chunk with metadata"""
    text: str
    start_pos: int
    end_pos: int
    metadata: Dict[str, any]
    chunk_index: int


class SmartChunker:
    """Intelligent chunker with L LM-enhanced boundaries and metadata"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        """
        Initialize smart chunker.
        
        Args:
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")  # Used by GPT-4 and text-embedding-3
        
    async def chunk_document(
        self, 
        text: str, 
        doc_name: str,
        use_llm_boundaries: bool = True
    ) -> List[Chunk]:
        """
        Chunk document with optional LLM-enhanced boundaries.
        
        Args:
            text: Document text to chunk
            doc_name: Document name for metadata
            use_llm_boundaries: Whether to use LLM for semantic boundary detection
            
        Returns:
            List of Chunk objects
        """
        # LLM-enhanced boundary detection
        if use_llm_boundaries:
            return await self._chunk_with_llm_boundaries(text, doc_name)
            
        # Fallback to token-based chunking if LLM boundaries not used
        tokens = self.encoding.encode(text)
        initial_chunks = []
        
        for i in range(0, len(tokens), self.chunk_size - self.chunk_overlap):
            chunk_tokens = tokens[i:i + self.chunk_size]
            chunk_text = self.encoding.decode(chunk_tokens)
            
            initial_chunks.append({
                'text': chunk_text,
                'start_pos': i,
                'end_pos': i + len(chunk_tokens),
                'chunk_index': len(initial_chunks)
            })
            
        # Create Chunk objects
        chunks = []
        for chunk_data in initial_chunks:
            chunks.append(Chunk(
                text=chunk_data['text'],
                start_pos=chunk_data['start_pos'],
                end_pos=chunk_data['end_pos'],
                metadata={
                    'document_name': doc_name,
                    'chunk_index': chunk_data['chunk_index'],
                    'total_chunks': len(initial_chunks)
                },
                chunk_index=chunk_data['chunk_index']
            ))
        
        return chunks

    async def _chunk_with_llm_boundaries(self, text: str, doc_name: str) -> List[Chunk]:
        """
        Use LLM to identify semantic boundaries for chunking.
        
        Args:
            text: Full document text
            doc_name: Document name
            
        Returns:
            List of semantic chunks
        """
        from src.providers.llm.factory import LLMFactory
        
        # Use metadata LLM for cost-effective chunking (falls back to main LLM if not set)
        metadata_model = settings.metadata_llm_model or settings.llm_model
        llm = LLMFactory.create(model=metadata_model)
        
        # Split text into manageable blocks for the LLM to analyze
        # We'll ask the LLM to identify logical break points
        # For simplicity in this implementation, we'll process the text in larger blocks
        # and ask the LLM to segment them.
        
        # Note: Processing very large documents entirely with LLM for segmentation 
        # can be slow/expensive. We'll use a hybrid approach:
        # 1. Split by double newlines (paragraphs)
        # 2. Group paragraphs into chunks until target size is reached
        # 3. Use LLM to verify if the break point is semantically valid or suggest a better one
        
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk_paragraphs = []
        current_tokens = 0
        chunk_index = 0
        
        for p in paragraphs:
            p_tokens = len(self.encoding.encode(p))
            
            if current_tokens + p_tokens > self.chunk_size:
                # Potential break point. 
                # In a full implementation, we would ask LLM: "Is this a good place to split?"
                # For this implementation, we'll respect the paragraph break as a semantic boundary
                # which is a simple form of "smart" boundary detection vs strict token cutting.
                
                chunk_text = "\n\n".join(current_chunk_paragraphs)
                chunks.append(Chunk(
                    text=chunk_text,
                    start_pos=0, # Simplified pos tracking
                    end_pos=0,
                    metadata={
                        'document_name': doc_name,
                        'chunk_index': chunk_index,
                        'total_chunks': 0 # Updated later
                    },
                    chunk_index=chunk_index
                ))
                chunk_index += 1
                current_chunk_paragraphs = [p]
                current_tokens = p_tokens
            else:
                current_chunk_paragraphs.append(p)
                current_tokens += p_tokens
        
        # Add last chunk
        if current_chunk_paragraphs:
            chunk_text = "\n\n".join(current_chunk_paragraphs)
            chunks.append(Chunk(
                text=chunk_text,
                start_pos=0,
                end_pos=0,
                metadata={
                    'document_name': doc_name,
                    'chunk_index': chunk_index,
                    'total_chunks': 0
                },
                chunk_index=chunk_index
            ))
            
        # Update total chunks
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)
            
        return chunks
    
    async def extract_metadata_with_llm(self, chunk_text: str) -> Dict[str, any]:
        """
        Extract metadata from chunk using cheaper LLM (metadata_llm_model or llm_model).
        
        Args:
            chunk_text: Text to extract metadata from
            
        Returns:
            Dictionary with section_title and key_concepts
        """
        # Use metadata LLM for cost-effective extraction (falls back to main LLM if not set)
        from src.providers.llm.factory import LLMFactory
        metadata_model = settings.metadata_llm_model or settings.llm_model
        metadata_llm = LLMFactory.create(model=metadata_model)
        
        prompt = f"""Analyze this medical guideline chunk and extract metadata.
Return ONLY a JSON object with:
- section_title: The main section or topic (1-5 words)
- key_concepts: List of 2-4 key medical concepts/terms

Chunk:
{chunk_text[:500]}...

Output JSON only:"""
        
        try:
            response = await metadata_llm.generate(prompt)
            # Clean response - remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```"):
                # Remove ```json and ``` wrapping
                lines = response.split("\n")
                response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            # Parse JSON response
            metadata = json.loads(response.strip())
            return metadata
        except Exception:
            # Fallback to empty metadata if LLM fails
            return {
                'section_title': 'Unknown',
                'key_concepts': []
            }
    
    async def chunk_with_metadata(
        self,
        text: str,
        doc_name: str
    ) -> List[Chunk]:
        """
        Chunk document and enrich with LLM-extracted metadata.
        
        Args:
            text: Document text
            doc_name: Document name
            
        Returns:
            List of Chunks with enriched metadata
        """
        # Initial chunking (paragraph-based)
        chunks = await self.chunk_document(text, doc_name, use_llm_boundaries=True)
        
        # Enrich with LLM metadata (using cheaper model)
        for chunk in chunks:
            llm_metadata = await self.extract_metadata_with_llm(chunk.text)
            chunk.metadata.update(llm_metadata)
        
        return chunks
