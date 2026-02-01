import asyncpg
from typing import AsyncGenerator

from ..core.config import settings


class Database:
    def __init__(self):
        self.pool = None

    async def create_pool(self):
        """Create a connection pool to the database"""
        self.pool = await asyncpg.create_pool(
            dsn=settings.DSN,
            min_size=5,
            max_size=20,
            command_timeout=60,
        )

    async def get_db_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a database connection from the pool"""
        if self.pool is None:
            raise Exception("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection

    async def close_pool(self):
        """Close the connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()


# Create a global database instance
db = Database()