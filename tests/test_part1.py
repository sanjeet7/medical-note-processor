"""
Unit tests for Part 1: FastAPI Backend Foundation

Tests all endpoints including health check and full CRUD operations.
Uses SQLite in-memory database for isolated testing.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database import Base, get_db
from src.models import Document

# Test database (SQLite in-memory for testing)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# Clean database before each test
@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test"""
    db = TestingSessionLocal()
    db.query(Document).delete()
    db.commit()
    db.close()

# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

def test_health_check():
    """Test health check returns {\"status\": \"ok\"}"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# ============================================================================
# DOCUMENT CRUD TESTS
# ============================================================================

def test_get_documents_empty():
    """Test GET /documents returns empty list when no documents"""
    response = client.get("/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 0

def test_create_document():
    """Test document creation with validation"""
    response = client.post("/documents", json={
        "title": "Test Document",
        "content": "Test content for medical note",
        "doc_type": "soap_note",
        "doc_metadata": {"patient_id": "patient-001"}
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Document"
    assert data["content"] == "Test content for medical note"
    assert data["doc_type"] == "soap_note"
    assert data["doc_metadata"]["patient_id"] == "patient-001"
    assert "id" in data
    assert "created_at" in data

def test_create_document_minimal():
    """Test document creation with minimal required fields"""
    response = client.post("/documents", json={
        "title": "Minimal Doc",
        "content": "Content"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Minimal Doc"
    assert data["doc_type"] == "general"
    assert data["doc_metadata"] == {}

def test_create_document_validation_error_empty_title():
    """Test validation rejects empty title"""
    response = client.post("/documents", json={
        "title": "",  # Invalid - too short
        "content": "Test content"
    })
    assert response.status_code == 422

def test_create_document_validation_error_missing_content():
    """Test validation rejects missing content"""
    response = client.post("/documents", json={
        "title": "Title only"
        # Missing content field
    })
    assert response.status_code == 422

def test_create_document_validation_error_title_too_long():
    """Test validation rejects title over 255 characters"""
    response = client.post("/documents", json={
        "title": "x" * 256,  # Too long
        "content": "Content"
    })
    assert response.status_code == 422

def test_get_documents_after_creation():
    """Test GET /documents returns IDs after creating documents"""
    # Create 3 documents
    for i in range(3):
        client.post("/documents", json={
            "title": f"Document {i+1}",
            "content": f"Content {i+1}"
        })
    
    response = client.get("/documents")
    assert response.status_code == 200
    doc_ids = response.json()
    assert len(doc_ids) == 3
    assert all(isinstance(doc_id, int) for doc_id in doc_ids)

def test_get_document_by_id():
    """Test retrieving specific document by ID"""
    # Create a document
    create_response = client.post("/documents", json={
        "title": "Test Doc",
        "content": "Test Content",
        "doc_type": "soap_note"
    })
    doc_id = create_response.json()["id"]
    
    # Retrieve it
    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["title"] == "Test Doc"
    assert data["content"] == "Test Content"
    assert data["doc_type"] == "soap_note"

def test_get_document_not_found():
    """Test 404 for non-existent document"""
    response = client.get("/documents/9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_update_document_partial():
    """Test document partial update"""
    # Create a document
    create_response = client.post("/documents", json={
        "title": "Original Title",
        "content": "Original content",
        "doc_type": "soap_note"
    })
    doc_id = create_response.json()["id"]
    
    # Update only title
    response = client.put(f"/documents/{doc_id}", json={
        "title": "Updated Title"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Original content"  # Should remain unchanged
    assert data["doc_type"] == "soap_note"      # Should remain unchanged

def test_update_document_full():
    """Test document full update"""
    # Create a document
    create_response = client.post("/documents", json={
        "title": "Original Title",
        "content": "Original content"
    })
    doc_id = create_response.json()["id"]
    
    # Update all fields
    response = client.put(f"/documents/{doc_id}", json={
        "title": "Updated Title",
        "content": "Updated content",
        "doc_type": "guideline",
        "doc_metadata": {"updated": True}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["content"] == "Updated content"
    assert data["doc_type"] == "guideline"
    assert data["doc_metadata"]["updated"] is True

def test_update_document_not_found():
    """Test 404 when updating non-existent document"""
    response = client.put("/documents/9999", json={
        "title": "Updated",
        "content": "Content"
    })
    assert response.status_code == 404

def test_delete_document():
    """Test document deletion"""
    # Create a document
    create_response = client.post("/documents", json={
        "title": "To Delete",
        "content": "Content to delete"
    })
    doc_id = create_response.json()["id"]
    
    # Delete it
    response = client.delete(f"/documents/{doc_id}")
    assert response.status_code == 204
    
    # Verify it's deleted
    get_response = client.get(f"/documents/{doc_id}")
    assert get_response.status_code == 404

def test_delete_document_not_found():
    """Test 404 when deleting non-existent document"""
    response = client.delete("/documents/9999")
    assert response.status_code == 404

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_crud_workflow():
    """Test complete CRUD workflow"""
    # 1. Start with empty database
    response = client.get("/documents")
    assert len(response.json()) == 0
    
    # 2. Create a document
    create_response = client.post("/documents", json={
        "title": "Workflow Test",
        "content": "Initial content",
        "doc_type": "soap_note"
    })
    assert create_response.status_code == 201
    doc_id = create_response.json()["id"]
    
    # 3. Verify it appears in list
    list_response = client.get("/documents")
    assert doc_id in list_response.json()
    
    # 4. Read the document
    read_response = client.get(f"/documents/{doc_id}")
    assert read_response.status_code == 200
    assert read_response.json()["title"] == "Workflow Test"
    
    # 5. Update the document
    update_response = client.put(f"/documents/{doc_id}", json={
        "title": "Updated Workflow Test",
        "content": "Updated content",
        "doc_type": "soap_note"
    })
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Workflow Test"
    
    # 6. Delete the document
    delete_response = client.delete(f"/documents/{doc_id}")
    assert delete_response.status_code == 204
    
    # 7. Verify it's gone
    final_list_response = client.get("/documents")
    assert doc_id not in final_list_response.json()
    assert len(final_list_response.json()) == 0

def test_multiple_documents():
    """Test handling multiple documents"""
    # Create 5 documents
    doc_ids = []
    for i in range(5):
        response = client.post("/documents", json={
            "title": f"Document {i+1}",
            "content": f"Content for document {i+1}",
            "doc_metadata": {"index": i+1}
        })
        doc_ids.append(response.json()["id"])
    
    # Verify all are in list
    list_response = client.get("/documents")
    assert len(list_response.json()) == 5
    
    # Verify each can be retrieved
    for doc_id in doc_ids:
        response = client.get(f"/documents/{doc_id}")
        assert response.status_code == 200
    
    # Delete one
    client.delete(f"/documents/{doc_ids[2]}")
    
    # Verify count
    list_response = client.get("/documents")
    assert len(list_response.json()) == 4

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
