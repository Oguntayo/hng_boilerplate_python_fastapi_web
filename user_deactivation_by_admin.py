import pytest
from fastapi.testclient import TestClient
from main import app  # Make sure this is the correct path to your FastAPI app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.db.database import Base, get_db

from api.v1.models.user import User  # Import the User model

from api.utils.auth import create_access_token


# Setup database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    # Create the tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    # Drop tables after test
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    # Return the TestClient
    return TestClient(app)


# Utility function to create a test user
def create_test_user(db):
    user = User(
        username="bayo",
        email="bayo@example.com",
        first_name="bayo",
        is_active=True,
        password="passwordbayo",  # Store password hash if needed, based on your app's user model
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_deactivate_account_success(client, db):
    # Create a test user
    user = create_test_user(db)

    # Prepare admin data (for simplicity, we are not focusing on authentication here, but you should include it)
    admin_token = create_access_token(data={"username": "admin"})

    # Make the request to deactivate the user
    response = client.patch(
        "/api/v1/users/deactivate",
        json={"username": user.username, "token": admin_token},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # Check that the status code is 200
    assert response.status_code == 200

    # Fetch the user from the DB again to check the changes
    db.refresh(user)
    assert user.is_active is False  # Ensure the user is deactivated

    # Check the response body
    assert response.json() == {
        "status": "success",
        "status_code": 200,
        "message": "User account deactivated successfully",
        "data": {}
    }


def test_deactivate_account_user_not_found(client, db):
    # Create a test user
    user = create_test_user(db)

    admin_token = create_access_token(data={"username": "admin"})

    # Try to deactivate a non-existing user
    response = client.patch(
        "/api/v1/users/deactivate",
        json={"username": "nonexistinguser", "token": admin_token},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 404
    assert response.json() == {
        "status": "error",
        "status_code": 404,
        "message": "User not found",
        "data": {}
    }


def test_deactivate_account_already_deactivated(client, db):
    # Create a test user
    user = create_test_user(db)
    user.is_active = False
    db.commit()  # Save the deactivated user

    admin_token = create_access_token(data={"username": "admin"})

    # Try to deactivate an already deactivated user
    response = client.patch(
        "/users/deactivate",
        json={"username": user.username, "token": admin_token},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 400
    assert response.json() == {
        "status": "error",
        "status_code": 400,
        "message": "User is already deactivated",
        "data": {}
    }
