from typing import Optional, Literal, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from api.core.dependencies.google_email import mail_service
from api.utils.config import SECRET_KEY, ALGORITHM
from api.utils.success_response import success_response
from api.v1.models.user import User
from api.v1.schemas.user import (
    DeactivateUserSchema, AdminDeactivateUserSchema,  
    AllUsersResponse, UserUpdate,  
    AdminCreateUserResponse, AdminCreateUser
)
from api.db.database import get_db
from api.utils.dependencies import get_current_user, get_current_admin
from api.v1.services.user import user_service
from uuid import UUID  

user_router = APIRouter(prefix="/users", tags=["Users"])


@user_router.patch('/deactivate', status_code=200)
async def deactivate_account(
    request: Request, schema: AdminDeactivateUserSchema, 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    '''Endpoint for admin to deactivate a user account'''
    
    user_to_deactivate = db.query(User).filter(User.username == schema.username).with_for_update().first()

    if user_to_deactivate is None:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "status_code": 404,
                "message": "User not found",
                "data": {}
            }
        )

    if not user_to_deactivate.is_active:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "status_code": 400,
                "message": "User is already deactivated",
                "data": {}
            }
        )

    db.query(User).filter(User.username == schema.username).update({"is_active": False})
    
    try:
        mail_service.send_mail(
            to=user_to_deactivate.email,
            subject='Account deactivation',
            body=f'Hello {user_to_deactivate.first_name},\n\nYour account has been deactivated successfully.\n\nTo reactivate your account if this was a mistake, please click the link below:\n{request.url.hostname}/api/v1/users/accounts/reactivate?token={schema.token}\n\nThis link expires after 15 minutes.'
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "status_code": 500,
                "message": f"Error sending email: {str(e)}",
                "data": {}
            }
        )

    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "status_code": 200,
            "message": "User account deactivated successfully",
            "data": {}
        }
    )


@user_router.patch("/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: str,
    current_user: Annotated[User, Depends(user_service.get_current_super_admin)],
    schema: UserUpdate,
    db: Session = Depends(get_db)
):
    user = user_service.update(db=db, schema=schema, id=user_id, current_user=current_user)

    return success_response(
        status_code=status.HTTP_200_OK,
        message='User Updated Successfully',
        data=jsonable_encoder(
            user,
            exclude=['password', 'is_superadmin', 'is_deleted', 'is_verified', 'updated_at', 'created_at', 'is_active']
        )
    )


@user_router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: str,
    current_user: Annotated[User, Depends(user_service.get_current_super_admin)],
    db: Session = Depends(get_db),
):
    """Endpoint for user deletion (soft-delete)"""

    user = user_service.fetch(db=db, id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_service.delete(db=db, id=user_id)

    return success_response(
        status_code=200,
        message='User deleted successfully',
    )


@user_router.get('', status_code=status.HTTP_200_OK, response_model=AllUsersResponse)
async def get_users(
    current_user: Annotated[User, Depends(user_service.get_current_super_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: int = 1, per_page: int = 10,
    is_active: Optional[bool] = Query(None),
    is_deleted: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    is_superadmin: Optional[bool] = Query(None)
):
    """
    Retrieves all users.
    """
    query_params = {
        'is_active': is_active,
        'is_deleted': is_deleted,
        'is_verified': is_verified,
        'is_superadmin': is_superadmin,
    }
    return user_service.fetch_all(db, page, per_page, **query_params)


@user_router.post("", status_code=status.HTTP_201_CREATED, response_model=AdminCreateUserResponse)
def admin_registers_user(
    user_request: AdminCreateUser,
    current_user: Annotated[User, Depends(user_service.get_current_super_admin)],
    db: Session = Depends(get_db)
):
    '''
    Endpoint for an admin to register a user.
    '''
    return user_service.super_admin_create_user(db, user_request)


@user_router.get('/{role_id}/roles', status_code=status.HTTP_200_OK)
async def get_users_by_role(
    role_id: Literal["admin", "user", "guest", "owner"], 
    db: Session = Depends(get_db), 
    current_user: User = Depends(user_service.get_current_user)
):
    '''Endpoint to get all users by role'''
    users = user_service.get_users_by_role(db, role_id, current_user)

    return success_response(
        status_code=200,
        message='Users retrieved successfully',
        data=jsonable_encoder(users)
    )


@user_router.get('/organisations', status_code=200, response_model=success_response)
def get_current_user_organisations(
    db: Session = Depends(get_db), 
    current_user: User = Depends(user_service.get_current_user)
):
    '''Endpoint to get all current user organisations'''

    return success_response(
        status_code=200,
        message='Organisations fetched successfully',
        data=jsonable_encoder(current_user.organisations)
    )


@user_router.get("/{user_id}", status_code=status.HTTP_200_OK)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(user_service.get_current_user)
):
    user = user_service.get_user_by_id(db=db, id=user_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message='User retrieved successfully',
        data=jsonable_encoder(
            user, 
            exclude=['password', 'is_superadmin', 'is_deleted', 'is_verified', 'updated_at', 'created_at', 'is_active']
        )
    )
