from typing import Optional
from datetime import datetime
import asyncpg
from ..core.config import settings


class ApiKey:
    def __init__(self, api_key_id: int, mentor_id: int, key_hash: str, key_prefix: str, 
                 name: str, description: Optional[str], created_at: datetime, 
                 last_used_at: Optional[datetime]):
        self.api_key_id = api_key_id
        self.mentor_id = mentor_id
        self.key_hash = key_hash
        self.key_prefix = key_prefix
        self.name = name
        self.description = description
        self.created_at = created_at
        self.last_used_at = last_used_at

    @classmethod
    def from_record(cls, record):
        return cls(
            api_key_id=record['api_key_id'],
            mentor_id=record['mentor_id'],
            key_hash=record['key_hash'],
            key_prefix=record['key_prefix'],
            name=record['name'],
            description=record.get('description'),
            created_at=record['created_at'],
            last_used_at=record.get('last_used_at')
        )

    async def save(self, connection: asyncpg.Connection, plain_key: str):
        """Save API key to database"""
        from ..core.security import hash_api_key
        
        # Hash the key before storing
        key_hash = hash_api_key(plain_key)
        
        query = f"""
            INSERT INTO {settings.DB_SCHEMA}.api_keys 
            (mentor_id, key_hash, key_prefix, name, description)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING api_key_id, mentor_id, key_hash, key_prefix, name, description, created_at, last_used_at
        """
        result = await connection.fetchrow(
            query,
            self.mentor_id,
            key_hash,
            self.key_prefix,
            self.name,
            self.description
        )
        return ApiKey.from_record(result)

    @classmethod
    async def get_by_id(cls, connection: asyncpg.Connection, api_key_id: int, mentor_id: int):
        """Get API key by ID and mentor_id (security check)"""
        query = f"""
            SELECT api_key_id, mentor_id, key_hash, key_prefix, name, description, created_at, last_used_at
            FROM {settings.DB_SCHEMA}.api_keys
            WHERE api_key_id = $1 AND mentor_id = $2
        """
        result = await connection.fetchrow(query, api_key_id, mentor_id)
        if result:
            return cls.from_record(result)
        return None

    @classmethod
    async def get_by_key_hash(cls, connection: asyncpg.Connection, key_hash: str):
        """Get API key by key hash"""
        query = f"""
            SELECT api_key_id, mentor_id, key_hash, key_prefix, name, description, created_at, last_used_at
            FROM {settings.DB_SCHEMA}.api_keys
            WHERE key_hash = $1
        """
        result = await connection.fetchrow(query, key_hash)
        if result:
            return cls.from_record(result)
        return None

    @classmethod
    async def get_all_by_mentor_id(cls, connection: asyncpg.Connection, mentor_id: int):
        """Get all API keys for a mentor"""
        query = f"""
            SELECT api_key_id, mentor_id, key_hash, key_prefix, name, description, created_at, last_used_at
            FROM {settings.DB_SCHEMA}.api_keys
            WHERE mentor_id = $1
            ORDER BY created_at DESC
        """
        results = await connection.fetch(query, mentor_id)
        return [cls.from_record(record) for record in results]

    @classmethod
    async def delete(cls, connection: asyncpg.Connection, api_key_id: int, mentor_id: int):
        """Delete API key by ID and mentor_id (security check)"""
        query = f"""
            DELETE FROM {settings.DB_SCHEMA}.api_keys 
            WHERE api_key_id = $1 AND mentor_id = $2
            RETURNING api_key_id
        """
        result = await connection.fetchval(query, api_key_id, mentor_id)
        return result is not None

    async def update_last_used(self, connection: asyncpg.Connection):
        """Update the last_used_at timestamp"""
        query = f"""
            UPDATE {settings.DB_SCHEMA}.api_keys
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE api_key_id = $1
        """
        await connection.execute(query, self.api_key_id)
        self.last_used_at = datetime.utcnow()
