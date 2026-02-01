from fastapi import APIRouter, Depends, HTTPException, status

from ...core.security import get_current_user, generate_api_key
from ...database.connection import db
from ...models.user import User
from ...schemas.user import ApiKeyCreate, ApiKeyResponse, ApiKeyCreateResponse
from ...models.api_key import ApiKey
from ...core.config import settings
from ...utils.logging import api_logger

router = APIRouter()


async def get_current_user_with_db(user: User = Depends(get_current_user)):
    """Get current user with access to database pool"""
    return user


@router.get("/api-keys/", response_model=list[ApiKeyResponse])
async def get_api_keys(current_user: User = Depends(get_current_user_with_db)):
    """
    Get all API keys for the current user
    """
    api_logger.log_user_action("Get API keys", current_user.username)
    
    async with db.pool.acquire() as connection:
        # Get mentor_id from username
        mentor_record = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
            current_user.username
        )
        
        if not mentor_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        mentor_id = mentor_record['mentor_id']
        
        # Get all API keys for this mentor
        api_keys = await ApiKey.get_all_by_mentor_id(connection, mentor_id)
        
        # Convert to response models (without full key and hash)
        return [
            ApiKeyResponse(
                api_key_id=key.api_key_id,
                name=key.name,
                description=key.description,
                key_prefix=key.key_prefix,
                created_at=key.created_at,
                last_used_at=key.last_used_at
            )
            for key in api_keys
        ]


@router.post("/api-keys/", response_model=ApiKeyCreateResponse)
async def create_api_key(
    api_key_data: ApiKeyCreate, 
    current_user: User = Depends(get_current_user_with_db)
):
    """
    Create a new API key for the current user
    """
    api_logger.log_user_action("Create API key", current_user.username, {"name": api_key_data.name})
    
    async with db.pool.acquire() as connection:
        # Get mentor_id from username
        mentor_record = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
            current_user.username
        )
        
        if not mentor_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        mentor_id = mentor_record['mentor_id']
        
        # Generate new API key
        plain_key = generate_api_key()
        key_prefix = plain_key[:8] + "..."  # Store first 8 chars for identification
        
        # Create API key object
        new_api_key = ApiKey(
            api_key_id=0,  # Will be set by database
            mentor_id=mentor_id,
            key_hash="",  # Will be set by save
            key_prefix=key_prefix,
            name=api_key_data.name,
            description=api_key_data.description,
            created_at=None,  # Will be set by database
            last_used_at=None
        )
        
        # Save to database (hashes the key)
        saved_key = await new_api_key.save(connection, plain_key)
        
        return ApiKeyCreateResponse(
            api_key_id=saved_key.api_key_id,
            name=saved_key.name,
            description=saved_key.description,
            key_prefix=saved_key.key_prefix,
            created_at=saved_key.created_at,
            last_used_at=saved_key.last_used_at,
            api_key=plain_key  # Only return the full key once
        )


@router.delete("/api-keys/{api_key_id}")
async def delete_api_key(
    api_key_id: int, 
    current_user: User = Depends(get_current_user_with_db)
):
    """
    Delete an API key by ID
    """
    api_logger.log_user_action("Delete API key", current_user.username, {"api_key_id": api_key_id})
    
    async with db.pool.acquire() as connection:
        # Get mentor_id from username
        mentor_record = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
            current_user.username
        )
        
        if not mentor_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        mentor_id = mentor_record['mentor_id']
        
        # Delete API key (will fail if api_key_id doesn't belong to this mentor)
        success = await ApiKey.delete(connection, api_key_id, mentor_id)
        
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        return {"message": "API key deleted successfully"}


@router.get("/api-keys/{api_key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    api_key_id: int, 
    current_user: User = Depends(get_current_user_with_db)
):
    """
    Get a specific API key by ID
    """
    api_logger.log_user_action("Get API key", current_user.username, {"api_key_id": api_key_id})
    
    async with db.pool.acquire() as connection:
        # Get mentor_id from username
        mentor_record = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
            current_user.username
        )
        
        if not mentor_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        mentor_id = mentor_record['mentor_id']
        
        # Get API key
        api_key = await ApiKey.get_by_id(connection, api_key_id, mentor_id)
        
        if not api_key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        
        return ApiKeyResponse(
            api_key_id=api_key.api_key_id,
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at
        )
