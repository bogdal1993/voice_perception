import asyncio
import asyncpg
import os
from datetime import datetime
from app.core.config import settings
from app.database.connection import db
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.schemas.call import CallFilter


async def test_database_connection():
    """Test database connection"""
    print("Testing database connection...")
    try:
        await db.create_pool()
        print("✓ Database connection pool created successfully")
        
        # Test a simple query
        async with db.pool.acquire() as connection:
            result = await connection.fetchval("SELECT 1")
            assert result == 1
            print("✓ Simple query executed successfully")
        
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
    finally:
        await db.close_pool()


async def test_user_model():
    """Test user model functionality"""
    print("\nTesting user model...")
    try:
        await db.create_pool()
        
        async with db.pool.acquire() as connection:
            # Create a test user
            test_username = "test_user"
            test_password = "test_password"
            hashed_password = get_password_hash(test_password)
            
            # Insert test user
            user_record = await connection.fetchrow(
                f"""
                INSERT INTO {settings.DB_SCHEMA}.mentors (username, password_hash, role)
                VALUES ($1, $2, $3)
                RETURNING mentor_id, username, role, is_active, created_at
                """,
                test_username, 
                hashed_password, 
                "user"
            )
            
            if user_record:
                print("✓ Test user created successfully")
                
                # Fetch the user back
                user = await User.get_by_username(connection, test_username)
                if user and user.username == test_username:
                    print("✓ User retrieved successfully")
                else:
                    print("✗ Failed to retrieve user")
                    return False
            
            # Clean up - delete test user
            await connection.execute(
                f"DELETE FROM {settings.DB_SCHEMA}.mentors WHERE username = $1",
                test_username
            )
            print("✓ Test user cleaned up")
        
        return True
    except Exception as e:
        print(f"✗ User model test failed: {e}")
        return False
    finally:
        await db.close_pool()


async def test_token_creation():
    """Test JWT token creation"""
    print("\nTesting token creation...")
    try:
        token_data = {"sub": "test_user", "role": "user"}
        token = create_access_token(token_data)
        
        if token and len(token) > 0:
            print("✓ JWT token created successfully")
            return True
        else:
            print("✗ Failed to create JWT token")
            return False
    except Exception as e:
        print(f"✗ Token creation test failed: {e}")
        return False


async def test_call_filter_validation():
    """Test call filter validation"""
    print("\nTesting call filter validation...")
    try:
        # Test creating a valid call filter
        call_filter = CallFilter(
            limit=10,
            offset=0,
            startDate=datetime.now(),
            endDate=datetime.now(),
            caller="%",
            callee="%"
        )
        
        if call_filter.limit == 10 and call_filter.offset == 0:
            print("✓ Call filter validation passed")
            return True
        else:
            print("✗ Call filter validation failed")
            return False
    except Exception as e:
        print(f"✗ Call filter validation test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    print("Running tests for refactored API...\n")
    
    tests = [
        test_database_connection,
        test_user_model,
        test_token_creation,
        test_call_filter_validation
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
    
    print(f"\nTest Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("✓ All tests passed! The refactored API is working correctly.")
        return True
    else:
        print("✗ Some tests failed. Please review the implementation.")
        return False


if __name__ == "__main__":
    # Set environment variables for testing if needed
    if not os.getenv("DSN"):
        print("Please set the DSN environment variable to run tests.")
        print("Example: DSN=postgresql://user:password@localhost/dbname")
    else:
        success = asyncio.run(run_all_tests())
        exit(0 if success else 1)