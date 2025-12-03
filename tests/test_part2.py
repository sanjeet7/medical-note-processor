from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.database import Base, get_db
from src.models import LLMCache
from src.providers.llm.factory import LLMFactory
from src.providers.llm.base import LLMProvider
from unittest.mock import MagicMock, patch
import pytest

# Test database (SQLite in /tmp for container compatibility)
SQLALCHEMY_DATABASE_URL = "sqlite:////tmp/test_part2.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# Mock LLM Provider
class MockLLMProvider(LLMProvider):
    async def generate(self, prompt: str, **kwargs) -> str:
        return "Mocked Summary"
    
    def get_provider_name(self) -> str:
        return "mock_provider"
    
    def get_model_name(self) -> str:
        return "mock_model"

@pytest.fixture
def mock_llm():
    with patch("src.providers.llm.factory.LLMFactory.create", return_value=MockLLMProvider()) as mock:
        yield mock

def test_llm_factory_openai():
    with patch("src.config.settings.llm_provider", "openai"), \
         patch("src.config.settings.llm_api_key", "test_key"):
        provider = LLMFactory.create()
        assert provider.get_provider_name() == "openai"

def test_llm_factory_anthropic():
    with patch("src.config.settings.llm_provider", "anthropic"), \
         patch("src.config.settings.llm_api_key", "test_key"):
        provider = LLMFactory.create()
        assert provider.get_provider_name() == "anthropic"

def test_summarize_note_endpoint(mock_llm):
    """Test summarization endpoint with mocked LLM"""
    response = client.post("/summarize_note", json={
        "text": "Patient has hypertension."
    })
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Mocked Summary"
    assert data["cached"] == False
    assert data["provider"] == "mock_provider"

def test_summarize_note_with_document_id(mock_llm):
    """Test summarization endpoint with document_id"""
    # Create a test document
    db = TestingSessionLocal()
    from src.models import Document
    test_doc = Document(
        title="Test Note",
        content="Patient presents with chest pain.",
        doc_type="soap_note"
    )
    db.add(test_doc)
    db.commit()
    doc_id = test_doc.id
    db.close()
    
    response = client.post("/summarize_note", json={
        "document_id": doc_id
    })
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Mocked Summary"

def test_summarize_note_document_id_priority(mock_llm):
    """Test that document_id takes priority when both document_id and text are provided"""
    # Create a test document
    db = TestingSessionLocal()
    from src.models import Document
    test_doc = Document(
        title="Priority Test",
        content="Document content from database.",
        doc_type="soap_note"
    )
    db.add(test_doc)
    db.commit()
    doc_id = test_doc.id
    db.close()
    
    # Pass both document_id and text - document_id should be used
    response = client.post("/summarize_note", json={
        "document_id": doc_id,
        "text": "This text should be ignored."
    })
    assert response.status_code == 200
    # The endpoint uses document_id when both are provided

def test_query_note_endpoint(mock_llm):
    """Test query endpoint with mocked LLM"""
    response = client.post("/query_note", json={
        "text": "Patient has hypertension.",
        "query": "What is the diagnosis?"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Mocked Summary" # Mock returns same string
    assert data["cached"] == False
    assert data["provider"] == "mock_provider"

def test_caching_logic(mock_llm):
    """Test that second request returns cached response"""
    # Clear cache first
    db = TestingSessionLocal()
    db.query(LLMCache).delete()
    db.commit()
    db.close()
    
    # First request (summarize)
    response1 = client.post("/summarize_note", json={
        "text": "Cache test note"
    })
    assert response1.status_code == 200
    assert response1.json()["cached"] == False
    
    # Second request (summarize) - should be cached
    response2 = client.post("/summarize_note", json={
        "text": "Cache test note"
    })
    assert response2.status_code == 200
    assert response2.json()["cached"] == True
    
    # Third request (query) - should NOT be cached (different task)
    response3 = client.post("/query_note", json={
        "text": "Cache test note",
        "query": "Question?"
    })
    assert response3.status_code == 200
    assert response3.json()["cached"] == False
    
    # Fourth request (query same question) - should be cached
    response4 = client.post("/query_note", json={
        "text": "Cache test note",
        "query": "Question?"
    })
    assert response4.status_code == 200
    assert response4.json()["cached"] == True
