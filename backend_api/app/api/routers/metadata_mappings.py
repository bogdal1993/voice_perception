import json
import re
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List

from ...core.security import get_current_admin_user
from ...database.connection import db
from ...schemas.call import (
    MetadataMappingCreate, 
    MetadataMappingUpdate, 
    MetadataMappingItem, 
    MetadataMappingFilter
)
from ...core.config import settings

router = APIRouter()

# Valid field types
VALID_FIELD_TYPES = {"text", "number", "date", "boolean", "json"}

# JSON path validation regex
JSON_PATH_REGEX = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*$')


def validate_field_key(field_key: str) -> bool:
    """Validate that the field_key is a valid JSON path"""
    return bool(JSON_PATH_REGEX.match(field_key))


def validate_field_type(field_type: str) -> bool:
    """Validate that the field_type is one of the allowed types"""
    return field_type in VALID_FIELD_TYPES


async def create_metadata_mapping_db(new_mapping: MetadataMappingCreate, current_user_id: int):
    """Create a new metadata mapping"""
    # Validate field_key
    if not validate_field_key(new_mapping.field_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="field_key must be a valid JSON path (e.g., 'customer.name' or 'call_duration')"
        )
    
    # Validate field_type
    if not validate_field_type(new_mapping.field_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"field_type must be one of: {', '.join(VALID_FIELD_TYPES)}"
        )
    
    async with db.pool.acquire() as connection:
        # Check if field_key already exists
        existing = await connection.fetchrow(
            f"SELECT mapping_id FROM {settings.DB_SCHEMA}.metadata_mappings WHERE field_key = $1",
            new_mapping.field_key
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mapping with field_key '{new_mapping.field_key}' already exists"
            )
        
        # Create the mapping
        row = await connection.fetchrow(
            f"""
            INSERT INTO {settings.DB_SCHEMA}.metadata_mappings 
            (field_key, display_name, field_type, is_active, sort_order, description, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING mapping_id, field_key, display_name, field_type, is_active, sort_order, 
                     created_at, created_by, description
            """,
            new_mapping.field_key,
            new_mapping.display_name,
            new_mapping.field_type,
            new_mapping.is_active,
            new_mapping.sort_order,
            new_mapping.description,
            current_user_id
        )
        # Convert Record to Pydantic model to ensure proper serialization
        if row:
            return MetadataMappingItem(
                mapping_id=row['mapping_id'],
                field_key=row['field_key'],
                display_name=row['display_name'],
                field_type=row['field_type'],
                is_active=row['is_active'],
                sort_order=row['sort_order'],
                created_at=row['created_at'],
                created_by=row['created_by'],
                description=row['description']
            )
        return row


async def update_metadata_mapping(mapping_id: int, updated_mapping: MetadataMappingUpdate, current_user_id: int):
    """Update an existing metadata mapping"""
    async with db.pool.acquire() as connection:
        # Check if mapping exists
        existing = await connection.fetchrow(
            f"SELECT mapping_id FROM {settings.DB_SCHEMA}.metadata_mappings WHERE mapping_id = $1",
            mapping_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mapping with ID {mapping_id} not found"
            )
        
        # Build update query dynamically
        update_fields = []
        update_values = []
        param_count = 1
        
        if updated_mapping.field_key is not None:
            if not validate_field_key(updated_mapping.field_key):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="field_key must be a valid JSON path (e.g., 'customer.name' or 'call_duration')"
                )
            
            # Check if field_key already exists for a different mapping
            conflict = await connection.fetchrow(
                f"SELECT mapping_id FROM {settings.DB_SCHEMA}.metadata_mappings WHERE field_key = $1 AND mapping_id != $2",
                updated_mapping.field_key,
                mapping_id
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Mapping with field_key '{updated_mapping.field_key}' already exists"
                )
            
            update_fields.append(f"field_key = ${param_count}")
            update_values.append(updated_mapping.field_key)
            param_count += 1
        
        if updated_mapping.display_name is not None:
            update_fields.append(f"display_name = ${param_count}")
            update_values.append(updated_mapping.display_name)
            param_count += 1
        
        if updated_mapping.field_type is not None:
            if not validate_field_type(updated_mapping.field_type):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"field_type must be one of: {', '.join(VALID_FIELD_TYPES)}"
                )
            update_fields.append(f"field_type = ${param_count}")
            update_values.append(updated_mapping.field_type)
            param_count += 1
        
        if updated_mapping.is_active is not None:
            update_fields.append(f"is_active = ${param_count}")
            update_values.append(updated_mapping.is_active)
            param_count += 1
        
        if updated_mapping.sort_order is not None:
            update_fields.append(f"sort_order = ${param_count}")
            update_values.append(updated_mapping.sort_order)
            param_count += 1
        
        if updated_mapping.description is not None:
            update_fields.append(f"description = ${param_count}")
            update_values.append(updated_mapping.description)
            param_count += 1
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Update the mapping
        update_values.append(mapping_id)  # WHERE clause parameter
        
        query = f"""
            UPDATE {settings.DB_SCHEMA}.metadata_mappings 
            SET {', '.join(update_fields)}
            WHERE mapping_id = ${param_count}
            RETURNING mapping_id, field_key, display_name, field_type, is_active, sort_order, 
                     created_at, created_by, description
        """
        
        row = await connection.fetchrow(query, *update_values)
        # Convert Record to Pydantic model to ensure proper serialization
        if row:
            return MetadataMappingItem(
                mapping_id=row['mapping_id'],
                field_key=row['field_key'],
                display_name=row['display_name'],
                field_type=row['field_type'],
                is_active=row['is_active'],
                sort_order=row['sort_order'],
                created_at=row['created_at'],
                created_by=row['created_by'],
                description=row['description']
            )
        return row


async def delete_metadata_mapping(mapping_id: int):
    """Delete a metadata mapping"""
    async with db.pool.acquire() as connection:
        # Check if mapping exists
        existing = await connection.fetchrow(
            f"SELECT mapping_id FROM {settings.DB_SCHEMA}.metadata_mappings WHERE mapping_id = $1",
            mapping_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mapping with ID {mapping_id} not found"
            )
        
        # Delete the mapping
        await connection.execute(
            f"DELETE FROM {settings.DB_SCHEMA}.metadata_mappings WHERE mapping_id = $1",
            mapping_id
        )


async def get_metadata_mappings_list(filter_params: MetadataMappingFilter):
    """Get list of metadata mappings with filtering"""
    async with db.pool.acquire() as connection:
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        
        # Build query dynamically based on filter parameters
        where_conditions = []
        query_params = []
        param_count = 1
        
        if filter_params.field_type:
            where_conditions.append(f"field_type = ${param_count}")
            query_params.append(filter_params.field_type)
            param_count += 1
        
        if filter_params.is_active is not None:
            where_conditions.append(f"is_active = ${param_count}")
            query_params.append(filter_params.is_active)
            param_count += 1
        
        if filter_params.search:
            where_conditions.append(
                f"(field_key ILIKE ${param_count} OR display_name ILIKE ${param_count + 1} OR description ILIKE ${param_count + 2})"
            )
            search_term = f"%{filter_params.search}%"
            query_params.extend([search_term, search_term, search_term])
            param_count += 3
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        query = f"""
            SELECT mapping_id, field_key, display_name, field_type, is_active, sort_order, 
                   created_at, created_by, description
            FROM {settings.DB_SCHEMA}.metadata_mappings
            {where_clause}
            ORDER BY sort_order, display_name
            LIMIT ${param_count} OFFSET ${param_count + 1}
        """
        
        query_params.extend([filter_params.limit, filter_params.offset])
        
        rows = await connection.fetch(query, *query_params)
        # Convert Record objects to Pydantic models to ensure proper serialization
        return [
            MetadataMappingItem(
                mapping_id=row['mapping_id'],
                field_key=row['field_key'],
                display_name=row['display_name'],
                field_type=row['field_type'],
                is_active=row['is_active'],
                sort_order=row['sort_order'],
                created_at=row['created_at'],
                created_by=row['created_by'],
                description=row['description']
            ) for row in rows
        ]


async def get_metadata_mapping_by_id(mapping_id: int):
    """Get a specific metadata mapping by ID"""
    async with db.pool.acquire() as connection:
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        
        row = await connection.fetchrow(
            f"""
            SELECT mapping_id, field_key, display_name, field_type, is_active, sort_order, 
                   created_at, created_by, description
            FROM {settings.DB_SCHEMA}.metadata_mappings
            WHERE mapping_id = $1
            """,
            mapping_id
        )
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mapping with ID {mapping_id} not found"
            )
        
        # Convert Record to Pydantic model to ensure proper serialization
        return MetadataMappingItem(
            mapping_id=row['mapping_id'],
            field_key=row['field_key'],
            display_name=row['display_name'],
            field_type=row['field_type'],
            is_active=row['is_active'],
            sort_order=row['sort_order'],
            created_at=row['created_at'],
            created_by=row['created_by'],
            description=row['description']
        )


async def get_metadata_for_call(call_uuid: str):
    """Get metadata for a specific call using active mappings"""
    async with db.pool.acquire() as connection:
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        
        # Get active mappings
        mappings = await connection.fetch(
            f"""
            SELECT field_key, display_name, field_type
            FROM {settings.DB_SCHEMA}.metadata_mappings
            WHERE is_active = true
            ORDER BY sort_order
            """
        )
        
        if not mappings:
            return {}
        
        # Get call metadata
        call_meta = await connection.fetchrow(
            f"""
            SELECT meta::json
            FROM {settings.DB_SCHEMA}.calls_meta
            WHERE call_uuid = $1
            """,
            call_uuid
        )
        
        if not call_meta or not call_meta['meta']:
            return {}
        
        # Apply mappings to extract and format metadata
        result = {}
        for mapping in mappings:
            field_key = mapping['field_key']
            display_name = mapping['display_name']
            field_type = mapping['field_type']
            
            try:
                # Navigate JSON path to get value
                value = call_meta['meta']
                for key in field_key.split('.'):
                    if isinstance(value, dict) and key in value:
                        value = value[key]
                    else:
                        value = None
                        break
                
                # Convert value based on field type
                if value is not None:
                    if field_type == 'number':
                        try:
                            value = float(value) if '.' in str(value) else int(value)
                        except (ValueError, TypeError):
                            value = str(value)
                    elif field_type == 'boolean':
                        value = bool(value)
                    elif field_type == 'date':
                        # Keep as string for now, could add date parsing if needed
                        value = str(value)
                    else:  # text or json
                        value = str(value)
                
                result[display_name] = value
                
            except (KeyError, TypeError, AttributeError):
                # If field path doesn't exist, skip it
                continue
        
        return result


async def get_active_metadata_mappings():
    """Get only active metadata mappings"""
    async with db.pool.acquire() as connection:
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        
        rows = await connection.fetch(
            f"""
            SELECT mapping_id, field_key, display_name, field_type, is_active, sort_order, 
                   created_at, created_by, description
            FROM {settings.DB_SCHEMA}.metadata_mappings
            WHERE is_active = true
            ORDER BY sort_order, display_name
            """
        )
        
        # Convert Record objects to Pydantic models to ensure proper serialization
        return [
            MetadataMappingItem(
                mapping_id=row['mapping_id'],
                field_key=row['field_key'],
                display_name=row['display_name'],
                field_type=row['field_type'],
                is_active=row['is_active'],
                sort_order=row['sort_order'],
                created_at=row['created_at'],
                created_by=row['created_by'],
                description=row['description']
            ) for row in rows
        ]


@router.get("/metadata-mappings/", response_model=List[MetadataMappingItem])
async def get_metadata_mappings_endpoint(
    field_type: Optional[str] = Query(None, description="Filter by field type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in field_key, display_name, or description"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user=Depends(get_current_admin_user)
):
    """
    Get all metadata mappings with pagination and filtering (admin only)
    """
    filter_params = MetadataMappingFilter(
        limit=limit,
        offset=offset,
        field_type=field_type,
        is_active=is_active,
        search=search
    )
    
    return await get_metadata_mappings_list(filter_params)


@router.post("/metadata-mappings/", response_model=MetadataMappingItem)
async def create_metadata_mapping_endpoint(
    new_mapping: MetadataMappingCreate,
    current_user=Depends(get_current_admin_user)
):
    """
    Create a new metadata mapping (admin only)
    """
    # Handle both cases: when current_user is an object with username attr or an integer ID
    from ...models.user import User as UserModel
    async with db.pool.acquire() as connection:
        if hasattr(current_user, 'username'):
            # current_user is a user object, get the ID from the database
            db_user = await UserModel.get_by_username(connection, current_user.username)
            if db_user:
                current_user_id = db_user.user_id
            else:
                # If user is not found in DB, raise an error as this should not happen for authenticated users
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User not found in database"
                )
        else:
            # current_user is already an integer ID
            current_user_id = current_user
    
    mapping = await create_metadata_mapping_db(new_mapping, current_user_id)
    return mapping


@router.put("/metadata-mappings/{mapping_id}", response_model=MetadataMappingItem)
async def update_metadata_mapping_endpoint(
    mapping_id: int,
    updated_mapping: MetadataMappingUpdate,
    current_user=Depends(get_current_admin_user)
):
    """
    Update an existing metadata mapping (admin only)
    """
    # Handle both cases: when current_user is an object with username attr or an integer ID
    from ...models.user import User as UserModel
    async with db.pool.acquire() as connection:
        if hasattr(current_user, 'username'):
            # current_user is a user object, get the ID from the database
            db_user = await UserModel.get_by_username(connection, current_user.username)
            if db_user:
                current_user_id = db_user.user_id
            else:
                # If user is not found in DB, raise an error as this should not happen for authenticated users
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User not found in database"
                )
        else:
            # current_user is already an integer ID
            current_user_id = current_user
    
    mapping = await update_metadata_mapping(mapping_id, updated_mapping, current_user_id)
    return mapping


@router.delete("/metadata-mappings/{mapping_id}")
async def delete_metadata_mapping_endpoint(
    mapping_id: int,
    current_user=Depends(get_current_admin_user)
):
    """
    Delete a metadata mapping (admin only)
    """
    await delete_metadata_mapping(mapping_id)
    return {"message": f"Metadata mapping {mapping_id} successfully deleted"}


@router.get("/metadata-mappings/call/{call_uuid}")
async def get_metadata_for_call_endpoint(
    call_uuid: str,
    current_user=Depends(get_current_admin_user)
):
    """
    Get metadata for a specific call using active mappings (admin only)
    """
    metadata = await get_metadata_for_call(call_uuid)
    return {"call_uuid": call_uuid, "metadata": metadata}


@router.get("/metadata-mappings/active", response_model=List[MetadataMappingItem])
async def get_active_metadata_mappings_endpoint(
    current_user=Depends(get_current_admin_user)
):
    """
    Get only active metadata mappings (admin only)
    """
    return await get_active_metadata_mappings()


@router.get("/metadata-mappings/active-public", response_model=List[MetadataMappingItem])
async def get_active_metadata_mappings_public_endpoint():
    """
    Get only active metadata mappings (public access for all users)
    """
    return await get_active_metadata_mappings()