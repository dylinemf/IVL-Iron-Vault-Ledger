import pytest
from sqlmodel import create_engine, Session, SQLModel
from fastapi.testclient import TestClient
from unittest.mock import MagicMock # Import MagicMock
from fastapi import BackgroundTasks # Import BackgroundTasks
from sqlalchemy.pool import StaticPool

from app.main import app # Import your FastAPI app
from app.models import Account, JournalEntry, User # Import your models
from app.db.session import get_session # Import get_session from app.db.session
from app.core.security import hash_password # Still needed for some test setup, maybe
from app.core.redis_client import get_redis_client # Import the dependency to override

# Setup an in-memory SQLite database for testing
@pytest.fixture(name="test_engine")
def test_engine_fixture():
    # Add check_same_thread=False for SQLite to allow multi-threaded access in tests
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine) # Clean up after tests

# Provide a fresh, transactional session for each test
@pytest.fixture(name="session")
def session_fixture(test_engine):
    with Session(test_engine) as session:
        # Create some dummy accounts for testing
        accounts = [
            Account(id=1, name="Swiss Asset", type="ASSET", country_code="CH", currency="CHF"),
            Account(id=2, name="Swiss Revenue", type="REVENUE", country_code="CH", currency="CHF"),
            Account(id=3, name="German Asset", type="ASSET", country_code="DE", currency="EUR"),
            Account(id=4, name="German Revenue", type="REVENUE", country_code="DE", currency="EUR"),
        ]
        for acc in accounts:
            session.add(acc)

        # Create a test user
        hashed_password = "$5$rounds=535000$ZfHKRMSnLav3EBzZ$8ViQVLkrgzhS4EjmRkJ/0dhOYHQia.9ZZTT1E8O1WQ0"
        test_user = User(username="testuser", hashed_password=hashed_password, full_name="Test User")
        session.add(test_user)

        session.commit() # Commit the initial data

        yield session

# We need a shared store for all redis mocks within a test session to be truly stateful
# This is a global dictionary (within the module scope of conftest)
_TEST_REDIS_STORE = {}

# Mock Redis client
@pytest.fixture(name="mock_redis_client")
def mock_redis_client_fixture():
    # Clear store for each fixture usage to ensure test isolation
    _TEST_REDIS_STORE.clear()

    mock_redis = MagicMock()
    # Mock get and set to interact with our shared store
    mock_redis.get.side_effect = lambda k: _TEST_REDIS_STORE.get(k)
    mock_redis.set.side_effect = lambda k, v, ex=None: _TEST_REDIS_STORE.update({k: v})

    return mock_redis

# Mock BackgroundTasks
@pytest.fixture(name="mock_background_tasks")
def mock_background_tasks_fixture():
    mock_tasks = MagicMock(spec=BackgroundTasks)
    # The list will store the added tasks as (func, args, kwargs) tuples
    mock_tasks.tasks = [] 
    mock_tasks.add_task.side_effect = lambda func, *args, **kwargs: mock_tasks.tasks.append((func, args, kwargs))
    return mock_tasks

@pytest.fixture(name="client")
def client_fixture(session: Session, mock_redis_client: MagicMock, mock_background_tasks: MagicMock):
    def get_session_override():
        return session
    
    def get_mock_redis_client_override():
        return mock_redis_client

    def get_mock_background_tasks_override():
        return mock_background_tasks

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_redis_client] = get_mock_redis_client_override # Override Redis client
    app.dependency_overrides[BackgroundTasks] = get_mock_background_tasks_override # Override BackgroundTasks
    
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear() # Clear overrides after test
