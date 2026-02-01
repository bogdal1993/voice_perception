from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from ...core.security import (
    create_access_token,
    verify_token,
    verify_password,
    get_password_hash,
    get_current_user,
    get_current_admin_user
)
from ...database.connection import db
from ...models.user import User
from ...schemas.user import UserCreate, UserInDB, Token
from ...core.config import settings
from ...utils.logging import api_logger

router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, gets an access token for future requests
    """
    async with db.pool.acquire() as connection:
        user_record = await connection.fetchrow(
            f"SELECT mentor_id, username, password_hash, role, is_active FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
            form_data.username
        )
        
        if not user_record or not verify_password(form_data.password, user_record['password_hash']) or not user_record['is_active']:
            api_logger.log_security_event("Failed login attempt", form_data.username, "unknown")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_record["username"], "role": user_record["role"]}, 
            expires_delta=access_token_expires
        )
        
        api_logger.log_user_action("Login", form_data.username)
        return {"access_token": access_token, "token_type": "bearer"}


@router.post("/users/", response_model=UserInDB)
async def create_user(
    user: UserCreate, 
    current_user: User = Depends(get_current_admin_user)
):
    """
    Create a new user (admin only)
    """
    api_logger.log_user_action("Create user", current_user.username, {"target_user": user.username})
    
    async with db.pool.acquire() as connection:
        # Check if user already exists
        existing_user = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
            user.username
        )
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
        
        # Hash the password
        hashed_password = get_password_hash(user.password)
        
        # Create new user
        new_user = await connection.fetchrow(
            f"""
            INSERT INTO {settings.DB_SCHEMA}.mentors (username, password_hash, role) 
            VALUES ($1, $2, $3) 
            RETURNING mentor_id as user_id, username, role, is_active, created_at
            """,
            user.username, 
            hashed_password, 
            user.role
        )
        
        if new_user:
            api_logger.log_user_action("User created successfully", current_user.username, {"user_id": new_user['user_id']})
            return UserInDB(**dict(new_user))
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")


@router.get("/users/", response_model=list[UserInDB])
async def get_users(
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get all users (admin only)
    """
    api_logger.log_user_action("Get all users", current_user.username)
    
    async with db.pool.acquire() as connection:
        rows = await connection.fetch(
            f"""
            SELECT mentor_id as user_id, username, role, is_active, created_at 
            FROM {settings.DB_SCHEMA}.mentors 
            ORDER BY created_at DESC
            """
        )
        # Convert asyncpg records to dictionaries
        return [UserInDB(**dict(row)) for row in rows]


@router.put("/users/{user_id}/password", response_model=dict)
async def change_password(
    user_id: int,
    new_password: str,
    current_user: User = Depends(get_current_user)
):
    """
    Change password for a specific user (admin can change any user's password, regular user can only change their own)
    """
    # Check if current user is admin OR they're trying to change their own password
    if current_user.role != "admin":
        # If not admin, verify that the user_id corresponds to the current user
        async with db.pool.acquire() as connection:
            user_record = await connection.fetchrow(
                f"SELECT mentor_id, username FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1",
                user_id
            )
            
            # Check if the target user exists and if it matches the current user
            if not user_record or user_record['username'] != current_user.username:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to change this user's password"
                )
    
    api_logger.log_user_action("Change password", current_user.username, {"target_user_id": user_id})
    
    async with db.pool.acquire() as connection:
        # Check if user exists
        existing_user = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1",
            user_id
        )
        if not existing_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # Hash the new password
        hashed_password = get_password_hash(new_password)
        
        # Update user's password
        await connection.execute(
            f"UPDATE {settings.DB_SCHEMA}.mentors SET password_hash = $1 WHERE mentor_id = $2",
            hashed_password,
            user_id
        )
        
        return {"message": "Password changed successfully"}

# Endpoint for users to change their own password
class ChangePasswordRequest(BaseModel):
    new_password: str


@router.put("/change-my-password", response_model=dict)
async def change_my_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Change the password of the current authenticated user
    """
    api_logger.log_user_action("Change own password", current_user.username, {"target_user": current_user.username})
    
    async with db.pool.acquire() as connection:
        # Get the current user's record by username to get their ID
        user_record = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1",
            current_user.username
        )
        
        if not user_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # Hash the new password
        hashed_password = get_password_hash(request.new_password)
        
        # Update user's password
        await connection.execute(
            f"UPDATE {settings.DB_SCHEMA}.mentors SET password_hash = $1 WHERE mentor_id = $2",
            hashed_password,
            user_record['mentor_id']
        )
        
        return {"message": "Password changed successfully"}
    
@router.delete("/users/{user_id}", response_model=dict)
async def delete_user(
    user_id: int, 
    current_user: User = Depends(get_current_admin_user)
):
    """
    Delete a user (admin only)
    """
    api_logger.log_user_action("Delete user", current_user.username, {"target_user_id": user_id})
    
    async with db.pool.acquire() as connection:
        # Check if user exists
        existing_user = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
            user_id
        )
        if not existing_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # Delete the user
        await connection.execute(f"DELETE FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", user_id)
        return {"message": "User deleted successfully"}