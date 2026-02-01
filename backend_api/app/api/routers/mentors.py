from fastapi import APIRouter, Depends, HTTPException, status

from ...core.security import get_current_admin_user
from ...database.connection import db
from ...schemas.call import MentorCreate, MentorPhoneAccess
from ...core.config import settings

router = APIRouter()


@router.post("/mentors/")
async def create_mentor(
    mentor_data: MentorCreate, 
    current_user=Depends(get_current_admin_user)
):
    """
    Create a new mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor already exists
            existing_mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1", 
                mentor_data.username
            )
            if existing_mentor:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mentor already exists")
            
            # Insert new mentor
            row = await connection.fetchrow(
                f"INSERT INTO {settings.DB_SCHEMA}.mentors (username) VALUES ($1) RETURNING mentor_id, username, created_at",
                mentor_data.username
            )
            return row
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating mentor: {str(e)}")


@router.get("/mentors/")
async def get_all_mentors(current_user=Depends(get_current_admin_user)):
    """
    Get all mentors (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            rows = await connection.fetch(
                f"SELECT mentor_id, username, created_at FROM {settings.DB_SCHEMA}.mentors ORDER BY created_at DESC"
            )
            # Convert asyncpg records to dictionaries to avoid serialization issues
            return [dict(row) for row in rows]
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching mentors: {str(e)}")


@router.get("/mentors/{mentor_id}")
async def get_mentor(
    mentor_id: int, 
    current_user=Depends(get_current_admin_user)
):
    """
    Get a specific mentor by ID (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            row = await connection.fetchrow(
                f"SELECT mentor_id, username, created_at FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            return row
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching mentor: {str(e)}")


@router.put("/mentors/{mentor_id}")
async def update_mentor(
    mentor_id: int, 
    mentor_data: MentorCreate, 
    current_user=Depends(get_current_admin_user)
):
    """
    Update a mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor exists
            existing_mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not existing_mentor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            
            # Update mentor username
            row = await connection.fetchrow(
                f"UPDATE {settings.DB_SCHEMA}.mentors SET username = $1 WHERE mentor_id = $2 RETURNING mentor_id, username, created_at",
                mentor_data.username, 
                mentor_id
            )
            return row
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating mentor: {str(e)}")


@router.delete("/mentors/{mentor_id}")
async def delete_mentor(
    mentor_id: int, 
    current_user=Depends(get_current_admin_user)
):
    """
    Delete a mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor exists
            existing_mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not existing_mentor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            
            # Delete the mentor (this will also delete related phone access records due to CASCADE)
            await connection.execute(f"DELETE FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", mentor_id)
            return {"message": "Mentor deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting mentor: {str(e)}")


@router.post("/mentors/{mentor_id}/phone-access/")
async def add_mentor_phone_access(
    mentor_id: int, 
    phone_access: MentorPhoneAccess, 
    current_user=Depends(get_current_admin_user)
):
    """
    Add phone access for a mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor exists
            mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not mentor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            
            # Check if this phone access already exists for this mentor
            existing_access = await connection.fetchrow(
                f"SELECT access_id FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 AND phone_number = $2",
                mentor_id, 
                phone_access.phone_number
            )
            if existing_access:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone access already exists for this mentor")
            
            # Insert new phone access record
            row = await connection.fetchrow(
                f"INSERT INTO {settings.DB_SCHEMA}.mentor_phone_access (mentor_id, phone_number) VALUES ($1, $2) RETURNING access_id, mentor_id, phone_number, created_at",
                mentor_id, 
                phone_access.phone_number
            )
            return row
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error adding phone access: {str(e)}")


@router.get("/mentors/{mentor_id}/phone-access/")
async def get_mentor_phone_access(
    mentor_id: int, 
    current_user=Depends(get_current_admin_user)
):
    """
    Get phone access records for a mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor exists
            mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not mentor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            
            # Get all phone access records for this mentor
            rows = await connection.fetch(
                f"SELECT access_id, mentor_id, phone_number, created_at FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 ORDER BY created_at DESC",
                mentor_id
            )
            return rows
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching phone access: {str(e)}")


@router.get("/mentors/{mentor_id}/phone-access/{access_id}")
async def get_mentor_phone_access_by_id(
    mentor_id: int, 
    access_id: int, 
    current_user=Depends(get_current_admin_user)
):
    """
    Get a specific phone access record for a mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor exists
            mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not mentor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            
            # Get specific phone access record
            row = await connection.fetchrow(
                f"SELECT access_id, mentor_id, phone_number, created_at FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 AND access_id = $2",
                mentor_id, 
                access_id
            )
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone access not found")
            return row
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching phone access: {str(e)}")


@router.delete("/mentors/{mentor_id}/phone-access/{access_id}")
async def delete_mentor_phone_access(
    mentor_id: int, 
    access_id: int, 
    current_user=Depends(get_current_admin_user)
):
    """
    Delete a phone access record for a mentor (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Check if mentor exists
            mentor = await connection.fetchrow(
                f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1", 
                mentor_id
            )
            if not mentor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mentor not found")
            
            # Check if phone access record exists and belongs to this mentor
            access_record = await connection.fetchrow(
                f"SELECT access_id FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 AND access_id = $2",
                mentor_id, 
                access_id
            )
            if not access_record:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone access not found")
            
            # Delete the phone access record
            await connection.execute(
                f"DELETE FROM {settings.DB_SCHEMA}.mentor_phone_access WHERE mentor_id = $1 AND access_id = $2",
                mentor_id, 
                access_id
            )
            return {"message": "Phone access deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error deleting phone access: {str(e)}")


# Endpoint to get distinct phone numbers for mentor access
@router.get("/phone-numbers/distinct/")
async def get_distinct_phone_numbers(current_user=Depends(get_current_admin_user)):
    """
    Get distinct phone numbers for mentor access (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Get distinct phone numbers from the calls table
            query = f"""
                SELECT DISTINCT caller as phone_number
                FROM {settings.DB_SCHEMA}.calls
                WHERE caller IS NOT NULL
                UNION
                SELECT DISTINCT calle as phone_number
                FROM {settings.DB_SCHEMA}.calls
                WHERE calle IS NOT NULL
                ORDER BY phone_number
            """
            rows = await connection.fetch(query)
            # Convert to list of phone numbers
            phone_numbers = [row['phone_number'] for row in rows if row['phone_number']]
            return phone_numbers
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching phone numbers: {str(e)}")


@router.get("/mentors/with-access/")
async def get_mentors_with_access(current_user=Depends(get_current_admin_user)):
    """
    Get all mentors with their phone access (admin only)
    """
    async with db.pool.acquire() as connection:
        try:
            # Get all mentors with their phone access
            query = f"""
                SELECT m.mentor_id, m.username, m.created_at,
                       CASE
                           WHEN COUNT(mpa.access_id) = 0 THEN '[]'::json
                           ELSE json_agg(
                               json_build_object(
                                   'access_id', mpa.access_id,
                                   'phone_number', mpa.phone_number,
                                   'created_at', mpa.created_at
                               )
                           )
                       END as phone_access
                FROM {settings.DB_SCHEMA}.mentors m
                LEFT JOIN {settings.DB_SCHEMA}.mentor_phone_access mpa ON m.mentor_id = mpa.mentor_id
                GROUP BY m.mentor_id, m.username, m.created_at
                ORDER BY m.created_at DESC
            """
            rows = await connection.fetch(query)
            # Convert to list of dicts
            import json
            result = []
            for row in rows:
                row_dict = dict(row)
                # Ensure phone_access is always an array
                if row_dict['phone_access'] is None:
                    row_dict['phone_access'] = []
                elif isinstance(row_dict['phone_access'], str):
                    # If it's a string representation of JSON, parse it
                    try:
                        row_dict['phone_access'] = json.loads(row_dict['phone_access'])
                    except (json.JSONDecodeError, TypeError):
                        row_dict['phone_access'] = []
                result.append(row_dict)
            return result
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching mentors with access: {str(e)}")