#!/usr/bin/env python3
"""
Indexing script for medical guidelines.
Loads guideline documents, chunks them with LLM-enhanced metadata,
generates embeddings, and stores in FAISS for RAG retrieval.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

def log(msg):
    """Print with immediate flush for Docker logs"""
    print(msg, flush=True)

async def index_guidelines():
    """Index medical guidelines into FAISS vector store"""
    
    log("🚀 Starting guideline indexing...")
    
    # Import dependencies
    try:
        from src.config import settings
        from src.rag.chunker import SmartChunker
        from src.rag.vector_store import FAISSVectorStore
        from src.providers.embeddings.factory import EmbeddingFactory
    except Exception as e:
        log(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Initialize components
    try:
        chunker = SmartChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        vector_store = FAISSVectorStore()
        embedding_provider = EmbeddingFactory.create()
    except Exception as e:
        log(f"❌ Initialization error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Clear existing collection (for re-indexing)
    vector_store.delete_collection()
    vector_store = FAISSVectorStore()  # Recreate
    
    # Find all guideline files
    guidelines_dir = Path(__file__).parent.parent / "data" / "medical_guidelines"
    guideline_files = list(guidelines_dir.glob("*.txt"))
    
    if not guideline_files:
        log("❌ No guideline files found!")
        return
    
    log(f"📄 Found {len(guideline_files)} guideline files")
    
    total_chunks = 0
    
    # Process each guideline
    for i, guideline_file in enumerate(sorted(guideline_files), 1):
        doc_name = guideline_file.stem
        log(f"   [{i}/{len(guideline_files)}] {doc_name}...")
        
        # Read document
        with open(guideline_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Chunk with LLM metadata extraction
        try:
            chunks = await chunker.chunk_with_metadata(text, doc_name)
        except Exception as e:
            log(f"      ❌ Chunking failed: {e}")
            continue
        
        # Generate embeddings
        try:
            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = await embedding_provider.embed_documents(chunk_texts)
        except Exception as e:
            log(f"      ❌ Embedding failed: {e}")
            continue
        
        # Store in vector database
        try:
            vector_store.add_documents(chunks, embeddings, doc_name)
        except Exception as e:
            log(f"      ❌ Storage failed: {e}")
            continue
        
        total_chunks += len(chunks)
    
    # Summary
    log("")
    log(f"✅ Indexing complete! {total_chunks} chunks from {len(guideline_files)} documents")


if __name__ == "__main__":
    asyncio.run(index_guidelines())
