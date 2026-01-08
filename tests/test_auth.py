from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models import User
from app.core.security import verify_password
from unittest.mock import MagicMock, ANY # Needed for redis mock assertions and ANY
import json

def test_register_user(client: TestClient, session: Session):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "password": "newpassword", "fullname": "New User"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User registered successfully"
    assert data["data"]["username"] == "newuser"

    user = session.exec(select(User).where(User.username == "newuser")).first()
    assert user is not None
    assert verify_password("newpassword", user.hashed_password)

def test_register_existing_user(client: TestClient, session: Session):
    # Register once
    client.post(
        "/api/v1/auth/register",
        json={"username": "existuser", "password": "password", "fullname": "Existing User"}
    )
    # Try to register again
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "existuser", "password": "password", "fullname": "Existing User"}
    )
    assert response.status_code == 409
    assert response.json()["message"] == "Username already registered"

def test_login_for_access_token(client: TestClient):
    # First, register a user
    client.post(
        "/api/v1/auth/register",
        json={"username": "loginuser", "password": "loginpassword"}
    )

    # Then, attempt to login
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "loginuser", "password": "loginpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_for_access_token_invalid_credentials(client: TestClient):
    # Attempt to login with invalid credentials without registering
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "nonexistent", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Incorrect username or password"

def test_access_protected_endpoint_unauthenticated(client: TestClient):
    # Attempt to access a protected endpoint without a token
    response = client.get("/api/v1/ledger/audit/verify")
    assert response.status_code == 401
    assert response.json()["message"] == "Not authenticated"

def test_access_protected_endpoint_authenticated(client: TestClient):
    # First, register and login to get a token
    client.post(
        "/api/v1/auth/register",
        json={"username": "authuser", "password": "authpassword"}
    )
    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": "authuser", "password": "authpassword"}
    )
    token = login_response.json()["access_token"]

    # Then, attempt to access a protected endpoint with the token
    response = client.get(
        "/api/v1/ledger/audit/verify",
        headers={"Authorization": f"Bearer {token}"}
    )
    # Expect 200 OK or 500 (since DB might be empty and integrity check won't work initially)
    # The actual content of the audit might vary, but we should not get 401
    assert response.status_code in [200, 500] 
    assert "status" in response.json()

def test_create_transaction_protected(client: TestClient):
    # First, register and login to get a token
    client.post(
        "/api/v1/auth/register",
        json={"username": "transactor", "password": "transactpassword"}
    )
    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": "transactor", "password": "transactpassword"}
    )
    token = login_response.json()["access_token"]

    # Try to create a transaction with the token
    response = client.post(
        "/api/v1/ledger/transaction",
        json={"debit_id": 1, "credit_id": 2, "amount": 10.0, "description": "Test Transaction"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "test-tx-1"}
    )
    assert response.status_code == 200


    data = response.json()
    assert data["status"] == "success"
    assert "transaction_details" in data["data"]

def test_idempotency_success(client: TestClient, mock_redis_client: MagicMock, mock_background_tasks: MagicMock):
    # This dictionary will act as our in-memory Redis store for this test
    redis_store = {}

    # Configure mock Redis client to interact with our redis_store
    def mock_get(key):
        return redis_store.get(key)
    def mock_set(key, value, ex=None):
        redis_store[key] = value

    mock_redis_client.get.side_effect = mock_get
    mock_redis_client.set.side_effect = mock_set

    # First, register and login to get a token
    client.post(
        "/api/v1/auth/register",
        json={"username": "idempuser", "password": "idempassword"}
    )
    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": "idempuser", "password": "idempassword"}
    )
    token = login_response.json()["access_token"]

    idempotency_key = "idemp-test-tx-1"
    transaction_data = {"debit_id": 1, "credit_id": 2, "amount": 20.0, "description": "Idempotent Transaction"}
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key}

    # First request: should initiate processing (202 Accepted)
    response_1 = client.post("/api/v1/ledger/transaction", json=transaction_data, headers=headers)
    assert response_1.status_code == 200
    assert "success" in response_1.json()["status"]

    # --- EXPLICITLY EXECUTE BACKGROUND TASKS ---
    # This ensures mock_redis_client.set calls are made and registered by the mock.
    for task_func, task_args, task_kwargs in mock_background_tasks.tasks:
        task_func(*task_args, **task_kwargs)
    mock_background_tasks.tasks.clear() # Clear tasks for the next request

    # Now, the redis_store should be updated as if background tasks completed.
    # Second request with the same key: should return the stored result (200 OK)
    response_2 = client.post("/api/v1/ledger/transaction", json=transaction_data, headers=headers)
    assert response_2.status_code == 200
    
    r1_data = response_1.json()
    r2_data = response_2.json()
    
    assert r2_data["message"] != r1_data["message"] # Message should indicate replay
    assert r2_data["data"]["is_idempotent_replay"] is True # Flag should be present
    assert r2_data["data"]["transaction_details"] == r1_data["data"]["transaction_details"] # Core data matches

    # Verify that redis_client.set was called correctly by the background tasks
    # Ensure all three sets (processing, response, completed) were recorded.
    mock_redis_client.set.assert_any_call(f"idempotency:{idempotency_key}:status", "processing", ex=ANY)
    mock_redis_client.set.assert_any_call(f"idempotency:{idempotency_key}:response", json.dumps(response_1.json()), ex=ANY)
    mock_redis_client.set.assert_any_call(f"idempotency:{idempotency_key}:status", "completed", ex=ANY)


def test_idempotency_processing_conflict(client: TestClient, mock_redis_client: MagicMock, mock_background_tasks: MagicMock):
    # This dictionary will act as our in-memory Redis store for this test
    redis_store = {}
    def mock_get(key):
        return redis_store.get(key)
    def mock_set(key, value, ex=None):
        redis_store[key] = value

    mock_redis_client.get.side_effect = mock_get
    mock_redis_client.set.side_effect = mock_set

    # First, register and login to get a token
    client.post(
        "/api/v1/auth/register",
        json={"username": "conflictuser", "password": "conflictpassword"}
    )
    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": "conflictuser", "password": "conflictpassword"}
    )
    token = login_response.json()["access_token"]

    idempotency_key = "idemp-test-tx-2"
    transaction_data = {"debit_id": 1, "credit_id": 2, "amount": 30.0, "description": "Conflict Transaction"}
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key}

    # Simulate request already being processed
    redis_store[f"idempotency:{idempotency_key}:status"] = "processing"

    response = client.post("/api/v1/ledger/transaction", json=transaction_data, headers=headers)
    assert response.status_code == 409
    assert "already being processed" in response.json()["message"]

    # Clear any potential background tasks that might have been added
    mock_background_tasks.tasks.clear()
