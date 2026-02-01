import asyncpg
from typing import List
from ..core.config import settings


async def check_user_phone_access(connection: asyncpg.Connection, username: str, phone_number: str) -> bool:
    """
    Check if a user has access to a specific phone number
    """
    # First, check if the user exists in the mentors table
    mentor_row = await connection.fetchrow(
        f"SELECT mentor_id, role FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
        username
    )
    
    if not mentor_row:
        # If user doesn't exist in mentors table, they have no restrictions (full access)
        return True
    
    # If user is admin, they have access to everything
    if mentor_row['role'] == 'admin':
        return True
    
    mentor_id = mentor_row['mentor_id']
    
    # Check if the user has access to this specific phone number
    access_row = await connection.fetchrow(
        f"SELECT access_id FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 AND phone_number = $2",
        mentor_id, 
        phone_number
    )
    
    if access_row:
        return True
    else:
        # Check if the phone number pattern matches (using LIKE operator)
        # This allows for partial matches like '%123%' for numbers containing '123'
        access_row = await connection.fetchrow(
            f"SELECT access_id FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 AND $2 LIKE phone_number",
            mentor_id, 
            phone_number
        )
        return access_row is not None


async def get_user_accessible_phones(connection: asyncpg.Connection, username: str) -> List[str]:
    """
    Get a list of phone numbers a user has access to
    """
    # First, check if the user exists in the mentors table
    mentor_row = await connection.fetchrow(
        f"SELECT mentor_id, role FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
        username
    )
    
    if not mentor_row:
        # If user doesn't exist in mentors table, they have no restrictions (full access)
        return ['%']  # Return wildcard to allow all numbers
    
    # If user is admin, they have access to all numbers
    if mentor_row['role'] == 'admin':
        return ['%']
    
    mentor_id = mentor_row['mentor_id']
    
    # Get all phone numbers the user has access to
    rows = await connection.fetch(
        f"SELECT phone_number FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1", 
        mentor_id
    )
    
    if not rows:
        # If no specific access defined, return empty list to block all access
        return []
    
    return [row['phone_number'] for row in rows]