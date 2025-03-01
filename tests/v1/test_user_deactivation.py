# import pytest
# from fastapi.testclient import TestClient
# from main import app
# from unittest.mock import MagicMock
# # from api.utils.auth import hash_password
# from api.v1.models.user import User
# from api.db.database import get_db

# client = TestClient(app)

# # Mock the database dependency
# @pytest.fixture
# def db_session_mock():
#     db_session = MagicMock()
#     yield db_session


# @pytest.fixture(autouse=True)
# def override_get_db(db_session_mock):
#     def get_db_override():
#         yield db_session_mock
#     app.dependency_overrides[get_db] = get_db_override

import sys
import os
import warnings

# DB_URL = os.getenv("DB_URL")

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
from api.utils.auth import hash_password
from api.v1.models.user import User
from api.v1.models.base import Base

# SQLALCHEMY_DATABASE_URL = config('DB_URL')
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db5"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)
# Suppress DeprecationWarnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Append the project root directory to the PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Override the get_db dependency to use the test database session
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create a test client for making requests to the FastAPI app
client = TestClient(app)

# Test DB fixture to clear the database before running tests
@pytest.fixture(scope="module")
def test_db():
    """Fixture to reset database before tests."""
    db = TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)  # Drop all tables
    Base.metadata.create_all(bind=engine)  # Recreate tables
    db.commit()
    yield db
    db.close()

# Helper function to create a user in the test database
def create_user(test_db):
    user = User(
        username="testuser",
        email="testuser@gmail.com",
        password=hash_password('Testpassword@123'),
        first_name='Test',
        last_name='User'
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

# Test function for user deactivation with missing fields
def error_user_deactivation(test_db):
    login = client.post('/api/v1/auth/login', data={
        "username": "testuser",
        "password": "Testpassword@123"
    })
    access_token = login.json()['access_token']

    missing_field = client.patch('/api/v1/users/accounts/deactivate', json={
        "reason": "No longer need the account"
    }, headers={'Authorization': f'Bearer {access_token}'})
    assert missing_field.status_code == 422

    confirmation_false = client.patch('/api/v1/users/accounts/deactivate', json={
        "reason": "No longer need the account",
        "confirmation": False
    }, headers={'Authorization': f'Bearer {access_token}'})
    assert confirmation_false.status_code == 400
    assert confirmation_false.json()['detail'] == 'Confirmation required to deactivate account'

    unauthorized = client.patch('/api/v1/users/accounts/deactivate', json={
        "reason": "No longer need the account",
        "confirmation": True
    })
    assert unauthorized.status_code == 401

# Test function for successful user deactivation
def success_deactivation_test(test_db):
    login = client.post('/auth/login', data={
        "username": "testuser",
        "password": "Testpassword@123"
    })
    access_token = login.json()['access_token']

    success_deactivation = client.patch('/api/v1/users/accounts/deactivate', json={
        "reason": "No longer need the account",
        "confirmation": True
    }, headers={'Authorization': f'Bearer {access_token}'})
    assert success_deactivation.status_code == 200

# Test function for user already deactivated
def test_user_inactive(test_db):
    # Create an inactive user
    user = User(
        username="testuser1",
        email="testuser1@gmail.com",
        password=hash_password('Testpassword@123'),
        first_name='Test',
        last_name='User',
        is_active=False,
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    login = client.post('/api/v1/auth/login', data={
        "username": "testuser1",
        "password": "Testpassword@123"
    })
    access_token = login.json().get('access_token')

    response = client.patch('/api/v1/users/accounts/deactivate', json={
        "reason": "No longer need the account",
        "confirmation": True
    }, headers={'Authorization': f'Bearer {access_token}'})
    assert response.status_code == 400
    assert response.json()['detail'] == 'User is inactive'

# Fixture to create a normal user
@pytest.fixture(scope="module")
def create_user(test_db):
    '''Create a normal user for testing'''
    user = User(
        username="testuser",
        email="testuser@gmail.com",
        password=hash_password('Testpassword@123'),
        first_name='Test',
        last_name='User'
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user

# Fixture to create an admin user
@pytest.fixture(scope="module")
def create_admin_user(test_db):
    '''Create an admin user for testing'''
    admin_user = User(
        username="adminuser2",
        email="adminuser2@example.com",
        password=hash_password('adminpassword'),
        first_name='Admin',
        last_name='User',
        is_admin=True,
        is_active=True
    )
    test_db.add(admin_user)
    test_db.commit()
    test_db.refresh(admin_user)
    return admin_user

# Test function for user deactivation when user not found
def test_deactivate_account_user_not_found(test_db, create_admin_user):
    '''Test for user not found when attempting to deactivate'''
    login = client.post('/api/v1/auth/login', data={
        "username": "adminuser2",  
        "password": "adminpassword"
    })
    access_token = login.json()['access_token']

    # Try to deactivate a user that doesn't exist
    response = client.patch('/api/v1/users/deactivate', json={
        "username": "nonexistentuserb",
        "confirmation": True,
        "token": access_token
    }, headers={'Authorization': f'Bearer {access_token}'})
    

    assert response.status_code == 404
    assert response.json()['message']== 'User not found'

# Test function for deactivating an already deactivated user
def test_deactivate_account_already_deactivated(test_db, create_admin_user):
    '''Test for user already deactivated'''
    # Add a user that is already inactive
    user = User(
        username="deactivateduserb",
        email="deactivateduserb@gmail.com",
        password=hash_password('Testpassword@123'),
        first_name='Test',
        last_name='User',
        is_active=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Admin login
    login = client.post('/api/v1/auth/login', data={
        "username": "adminuser2",  # Admin to deactivate users
        "password": "adminpassword"
    })
    access_token = login.json()['access_token']

    # Try to deactivate an already deactivated user
    response = client.patch('/api/v1/users/deactivate', json={
        "username": "deactivateduserb",
        "confirmation": True,
        "token": access_token
    }, headers={'Authorization': f'Bearer {access_token}'})
    

    assert response.status_code == 400
    assert response.json()['message'] == 'User is already deactivated'

# Test function for successful deactivation of an active user
from unittest import mock
from api.core.dependencies.email import mail_service

def test_successful_deactivation(test_db, create_admin_user):
    '''Test for successful user deactivation'''
    
    # Add a user that is active
    user = User(
        username="activeuserbb",
        email="activeuserbb@gmail.com",
        password=hash_password('Testpasswordb@123'),
        first_name='Testb',
        last_name='Userb',
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Admin login
    login = client.post('/api/v1/auth/login', data={
        "username": "adminuser2",  # Admin to deactivate users
        "password": "adminpassword"
    })
    access_token = login.json()['access_token']

    # Mock the send_mail method to avoid real email sending
    with mock.patch.object(mail_service, 'send_mail', return_value=True):
        # Try to deactivate an active user
        response = client.patch('/api/v1/users/deactivate', json={
            "username": "activeuserbb",
            "confirmation": True,
            "token": access_token
        }, headers={'Authorization': f'Bearer {access_token}'})
        
    assert response.status_code == 200
    assert response.json()['message'] == 'User account deactivated successfully'
