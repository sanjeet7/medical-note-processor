#!/usr/bin/env python3
"""
Database seeding script for SOAP notes

This script loads the 6 SOAP notes from data/soap_notes/ 
into the PostgreSQL database for testing and demonstration.

Usage:
    python scripts/seed_database.py
"""
import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.append(str(Path(__file__).parent.parent))

from src.database import SessionLocal, engine
from src.models import Base, Document

# Create all tables
Base.metadata.create_all(bind=engine)

def seed_soap_notes():
    """Load 6 SOAP notes from data/soap_notes/ into database"""
    db = SessionLocal()
    
    soap_notes = []
    notes_dir = Path(__file__).parent.parent / "data" / "soap_notes"
    
    # Check if directory exists
    if not notes_dir.exists():
        print(f"⚠️  SOAP notes directory not found: {notes_dir}")
        print("   Please ensure data/soap_notes/ directory exists with SOAP note files")
        return
    
    # Read all SOAP note files
    note_files = sorted(notes_dir.glob("soap_*.txt"))
    if not note_files:
        print(f"⚠️  No SOAP note files found in {notes_dir}")
        return
    
    for note_file in note_files:
        with open(note_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        title = f"SOAP Note - {note_file.stem}"
        
        # Extract patient and date from first lines if available
        lines = content.strip().split('\n')
        metadata = {}
        for line in lines[:5]:  # Check first few lines
            if line.startswith("Patient:"):
                metadata['patient_id'] = line.replace("Patient:", "").strip()
            elif "Encounter Date:" in line or "Date:" in line:
                # Extract date from line
                date_part = line.split("Date:")[-1].strip()
                metadata['encounter_date'] = date_part
        
        soap_notes.append({
            "title": title,
            "content": content,
            "doc_type": "soap_note",
            "doc_metadata": metadata
        })
    
    # Insert into database (skip if already exists)
    added_count = 0
    skipped_count = 0
    
    for note in soap_notes:
        existing = db.query(Document).filter(Document.title == note["title"]).first()
        if not existing:
            db_note = Document(**note)
            db.add(db_note)
            print(f"✓ Added: {note['title']}")
            added_count += 1
        else:
            print(f"⊘ Skipped (exists): {note['title']}")
            skipped_count += 1
    
    db.commit()
    db.close()
    
    print(f"\n✅ Database seeding complete!")
    print(f"   Added: {added_count} SOAP notes")
    print(f"   Skipped: {skipped_count} existing notes")
    print(f"   Total: {len(soap_notes)} SOAP notes in database")

if __name__ == "__main__":
    print("📋 Seeding database with SOAP notes...\n")
    try:
        seed_soap_notes()
    except Exception as e:
        print(f"\n❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
