from typing import Optional
from datetime import datetime
import asyncpg
from ..core.config import settings


class User:
    def __init__(self, user_id: int, username: str, role: str, is_active: bool, created_at: datetime):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.is_active = is_active
        self.created_at = created_at

    @classmethod
    def from_record(cls, record):
        return cls(
            user_id=record['user_id'] if 'user_id' in record else record['mentor_id'],
            username=record['username'],
            role=record['role'],
            is_active=record['is_active'],
            created_at=record['created_at']
        )

    async def save(self, connection: asyncpg.Connection):
        """Save user to database"""
        query = f"""
            INSERT INTO {settings.DB_SCHEMA}.mentors (username, password_hash, role, is_active)
            VALUES ($1, $2, $3, $4)
            RETURNING mentor_id, username, role, is_active, created_at
        """
        result = await connection.fetchrow(
            query,
            self.username,
            self.password_hash,
            self.role,
            self.is_active
        )
        return User.from_record(result)

    @classmethod
    async def get_by_username(cls, connection: asyncpg.Connection, username: str):
        """Get user by username"""
        query = f"""
            SELECT mentor_id as user_id, username, role, is_active, created_at
            FROM {settings.DB_SCHEMA}.mentors
            WHERE username = $1
        """
        result = await connection.fetchrow(query, username)
        if result:
            return cls.from_record(result)
        return None

    @classmethod
    async def get_by_id(cls, connection: asyncpg.Connection, user_id: int):
        """Get user by ID"""
        query = f"""
            SELECT mentor_id as user_id, username, role, is_active, created_at
            FROM {settings.DB_SCHEMA}.mentors
            WHERE mentor_id = $1
        """
        result = await connection.fetchrow(query, user_id)
        if result:
            return cls.from_record(result)
        return None

    @classmethod
    async def authenticate(cls, connection: asyncpg.Connection, username: str, password: str, password_hash: str):
        """Authenticate user with password"""
        from ..core.security import verify_password
        
        user = await cls.get_by_username(connection, username)
        if user and verify_password(password, password_hash) and user.is_active:
            return user
        return None

    @classmethod
    async def get_all(cls, connection: asyncpg.Connection, limit: int = 100, offset: int = 0):
        """Get all users"""
        query = f"""
            SELECT mentor_id as user_id, username, role, is_active, created_at
            FROM {settings.DB_SCHEMA}.mentors
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        results = await connection.fetch(query, limit, offset)
        return [cls.from_record(record) for record in results]

    @classmethod
    async def delete(cls, connection: asyncpg.Connection, user_id: int):
        """Delete user by ID"""
        query = f"DELETE FROM {settings.DB_SCHEMA}.mentors WHERE mentor_id = $1"
        await connection.execute(query, user_id)
        return True

    @classmethod
    async def create_default_admin(cls, connection: asyncpg.Connection):
        """Create default admin user if not exists"""
        from ..core.security import get_password_hash
        
        # Check if admin user already exists
        admin_exists = await connection.fetchrow(
            f"SELECT mentor_id FROM {settings.DB_SCHEMA}.mentors WHERE username = $1 AND role = $2",
            "admin",
            "admin"
        )
        
        if not admin_exists:
            # Create admin user with default password
            default_password = "admin123"[:72]
            hashed_password = get_password_hash(default_password)
            
            query = f"""
                INSERT INTO {settings.DB_SCHEMA}.mentors (username, password_hash, role)
                VALUES ($1, $2, $3)
                RETURNING mentor_id, username, role, is_active, created_at
            """
            result = await connection.fetchrow(
                query,
                "admin",
                hashed_password,
                "admin"
            )
            print("Default admin user created with username: admin and password: admin123")
            return cls.from_record(result)
        
        return None