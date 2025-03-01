import sys
import os
import warnings

# Ignore deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Append the project root directory to the PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decouple import config
from main import app
from api.db.database import Base, get_db
from api.v1.services.user import user_service
from api.v1.models.user import User


# SQLite Test Database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db5"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Drop and recreate tables before tests

Base.metadata.create_all(bind=engine)

# Override database dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

url = "/api/v1"
@pytest.fixture(scope="module")
def test_db():
    """Fixture to reset database before tests."""
    db = TestingSessionLocal()
    
    Base.metadata.create_all(bind=engine)  # Recreate tables
    db.commit()
    yield db
    db.close()

def create_user(username: str, password: str):
    """Create a new user only if it doesn't exist."""
    check_response = client.get(f"{url}/users/{username}")  # Check if user exists
    if check_response.status_code == 200:
        print(f"User '{username}' already exists, skipping creation.")
        return check_response.json()

    user_data = {
        "username": username,
        "password": password,
        "first_name": "kama",
        "last_name": "mba",
        "email": f"{username}@example.com",
        "is_admin": True
    }

    response = client.post(f"{url}/auth/register", json=user_data)
    print("User Creation Response:", response.json())
    assert response.status_code == 201  # Expect user creation success
    return response.json()

def get_auth_token(username: str, password: str):
    """Get authentication token for a user."""
    login_data = {
        "username": username,
        "password": password
    }
    response = client.post(f"{url}/auth/login", data=login_data)
    print("Login Response:", response.json())
    assert response.status_code == 200
    return response.json()["access_token"]

def create_permission(name: str, token: str):
    """Create a new permission."""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"name": name}
    response = client.post(f"{url}/permissions", headers=headers, json=data)
    print("Permission Response:", response.json())
    assert response.status_code == 201
    return response.json()

def create_organization(name: str, desc: str, token: str):
    """Create an organization."""
    headers = {"Authorization": f"Bearer {token}"}
    org_data = {"name": name, "description": desc}
    response = client.post(f"{url}/organizations", json=org_data, headers=headers)
    print("Organization Response:", response.json())
    assert response.status_code == 201
    return response.json()["id"]

def create_role(token: str, role_name: str, organization_id: str, permission_ids: list = None):
    """Create a new role."""
    headers = {"Authorization": f"Bearer {token}"}
    role_data = {
        "role_name": role_name,
        "organization_id": organization_id,
        "permission_ids": permission_ids
    }
    response = client.post(f"{url}/roles", headers=headers, json=role_data)
    print("Role Response:", response.json())
    assert response.status_code == 201
    return response.json()

def test_create_role():
    """Test creating a role with an authenticated user."""
    
    # Create a user
    username = "admin"
    password = "admin12345"
    create_user(username=username, password=password)
    
    # Get authentication token
    token = get_auth_token(username=username, password=password)

    # Create an organization
    organization_id = create_organization(desc="Test Organization", name="Mba", token=token)

    # Create a permission
    permission = create_permission(name="Read", token=token)

    # Create a role
    role_name = "Manager1"
    permission = ["Read"]
    create_role(token=token, role_name=role_name, organization_id=organization_id, permission_ids=permission)
