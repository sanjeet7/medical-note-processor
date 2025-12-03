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

from src.rag.chunker import SmartChunker
from src.rag.vector_store import FAISSVectorStore
from src.providers.embeddings.factory import EmbeddingFactory  
from src.config import settings


async def index_guidelines():
    """Index medical guidelines into FAISS vector store"""
    
    print("🚀 Starting guideline indexing...")
    print(f"📁 Loading guidelines from: data/medical_guidelines/")
    print(f"⚙️  Chunk size: {settings.chunk_size} tokens, Overlap: {settings.chunk_overlap} tokens")
    print(f"🤖 Metadata LLM: {settings.metadata_llm_model}")
    print(f"🔢 Embedding model: {settings.embedding_model}\n")
    
    # Initialize components
    chunker = SmartChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap
    )
    vector_store = FAISSVectorStore()
    embedding_provider = EmbeddingFactory.create()
    
    # Clear existing collection (for re-indexing)
    print("🗑️  Clearing existing collection...")
    vector_store.delete_collection()
    vector_store = FAISSVectorStore()  # Recreate
    
    # Find all guideline files
    guidelines_dir = Path(__file__).parent.parent / "data" / "medical_guidelines"
    guideline_files = list(guidelines_dir.glob("*.txt"))
    
    if not guideline_files:
        print("❌ No guideline files found!")
        return
    
    print(f"📄 Found {len(guideline_files)} guideline files\n")
    
    total_chunks = 0
    
    # Process each guideline
    for guideline_file in sorted(guideline_files):
        doc_name = guideline_file.stem
        print(f"📖 Processing: {doc_name}")
        
        # Read document
        with open(guideline_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Chunk with LLM metadata extraction
        print(f"   ✂️  Chunking (with LLM metadata extraction)...")
        chunks = await chunker.chunk_with_metadata(text, doc_name)
        print(f"   ✅ Created {len(chunks)} chunks")
        
        # Generate embeddings
        print(f"   🔢 Generating embeddings...")
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await embedding_provider.embed_documents(chunk_texts)
        print(f"   ✅ Generated {len(embeddings)} embeddings")
        
        # Store in vector database
        print(f"   💾 Storing in FAISS...")
        vector_store.add_documents(chunks, embeddings, doc_name)
        print(f"   ✅ Stored {len(chunks)} chunks\n")
        
        total_chunks += len(chunks)
    
    # Summary
    collection_count = vector_store.get_collection_count()
    print("=" * 60)
    print(f"✅ Indexing complete!")
    print(f"📚 Indexed {len(guideline_files)} documents")
    print(f"📊 Total chunks: {total_chunks}")
    print(f"💾 Chunks in FAISS: {collection_count}")
    print(f"📂 Persisted to: {settings.faiss_db_path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(index_guidelines())
