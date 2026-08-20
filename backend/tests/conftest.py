import os
import pytest
from pathlib import Path

# Configure environment variables for test execution to use a file-based test DB
TEST_DB_PATH = Path(__file__).parent.parent / "test_prompt_classifier.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.resolve()}"
os.environ["LLM_API_KEY"] = "placeholder"
os.environ["LLM_BASE_URL"] = ""
os.environ["CLASSIFIER_MODEL"] = "gpt-4o-mini"

from fastapi.testclient import TestClient
from app.models import Base
from app import session_store
from app.main import app

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Creates tables in the file-based test database on test suite initialization.
    Cleans up the database file when the suite finishes.
    """
    # Remove existing test DB if any
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass
            
    Base.metadata.create_all(bind=session_store.engine)
    yield
    Base.metadata.drop_all(bind=session_store.engine)
    
    # Close any open connections in engine before deleting file
    session_store.engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass

@pytest.fixture(autouse=True)
def clear_db():
    """
    Clears table contents between test executions to isolate test cases.
    """
    yield
    db = session_store.SessionLocal()
    try:
        db.execute(Base.metadata.tables["prompt_records"].delete())
        db.execute(Base.metadata.tables["sessions"].delete())
        db.commit()
    finally:
        db.close()

@pytest.fixture
def client():
    """
    Standard FastAPI TestClient.
    """
    return TestClient(app)
