#!/usr/bin/env python3
"""
Test script to demonstrate the mentor authentication setup.
This script shows how to add mentors and configure their phone number access.
"""

import asyncpg
import os
import asyncio
from typing import List

SCHEMA_NAME = os.getenv('DB_SCHEMA', 'vp') # Default to 'vp' if not specified

DSN = os.getenv('DSN', 'postgresql://postgres:postgres@localhost:5432/postgres')

async def setup_test_data():
    """Setup test mentors and phone access for demonstration"""
    conn = await asyncpg.connect(DSN)
    
    try:
        # Add test mentors
        print("Adding test mentors...")
        mentor1 = await conn.fetchrow(
            f"INSERT INTO {SCHEMA_NAME}.mentors (username) VALUES ($1) ON CONFLICT (username) DO UPDATE SET username = $1 RETURNING mentor_id, username",
            "mentor1"
        )
        print(f"Added mentor: {mentor1}")
        
        mentor2 = await conn.fetchrow(
            f"INSERT INTO {SCHEMA_NAME}.mentors (username) VALUES ($1) ON CONFLICT (username) DO UPDATE SET username = $1 RETURNING mentor_id, username",
            "mentor2"
        )
        print(f"Added mentor: {mentor2}")
        
        # Add phone access for mentor1
        print("\nAdding phone access for mentor1...")
        await conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.mentor_phone_access (mentor_id, phone_number) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            mentor1['mentor_id'], "+1234567890"
        )
        await conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.mentor_phone_access (mentor_id, phone_number) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            mentor1['mentor_id'], "+0987654321"
        )
        
        # Add phone access for mentor2
        print("Adding phone access for mentor2...")
        await conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.mentor_phone_access (mentor_id, phone_number) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            mentor2['mentor_id'], "+111111"
        )
        await conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.mentor_phone_access (mentor_id, phone_number) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            mentor2['mentor_id'], "+2222"
        )
        
        # Show the configuration
        print("\nMentor configurations:")
        mentors = await conn.fetch(f"SELECT mentor_id, username FROM {SCHEMA_NAME}.mentors")
        for mentor in mentors:
            print(f"\nMentor: {mentor['username']} (ID: {mentor['mentor_id']})")
            phones = await conn.fetch(
                f"SELECT phone_number FROM {SCHEMA_NAME}.mentor_phone_access WHERE mentor_id = $1",
                mentor['mentor_id']
            )
            if phones:
                for phone in phones:
                    print(f"  - Phone: {phone['phone_number']}")
            else:
                print("  - No phone access configured")
                
    finally:
        await conn.close()

async def test_access_logic():
    """Test the access logic that's implemented in the backend"""
    conn = await asyncpg.connect(DSN)
    
    try:
        print("\n" + "="*50)
        print("TESTING ACCESS LOGIC")
        print("="*50)
        
        # Test user phone access function
        async def get_user_accessible_phones(username: str):
            """Simulate the function from main.py"""
            mentor_row = await conn.fetchrow(
                f"SELECT mentor_id FROM {SCHEMA_NAME}.mentors WHERE username = $1", username
            )
            if not mentor_row:
                # If user doesn't exist in mentors table, they have no restrictions (full access)
                return ['%']  # Return wildcard to allow all numbers
            
            mentor_id = mentor_row['mentor_id']
            
            # Get all phone numbers the user has access to
            rows = await conn.fetch(
                f"SELECT phone_number FROM {SCHEMA_NAME}.mentor_phone_access WHERE mentor_id = $1", mentor_id
            )
            if not rows:
                # If no specific access defined, return empty list to block all access
                return []
            
            return [row['phone_number'] for row in rows]
        
        # Test with mentor1
        mentor1_phones = await get_user_accessible_phones("mentor1")
        print(f"Mentor1 accessible phones: {mentor1_phones}")
        
        # Test with mentor2
        mentor2_phones = await get_user_accessible_phones("mentor2")
        print(f"Mentor2 accessible phones: {mentor2_phones}")
        
        # Test with non-existent mentor (should have full access)
        other_user_phones = await get_user_accessible_phones("nonexistent_user")
        print(f"Non-existent user accessible phones: {other_user_phones}")
        
        # Test access check function
        async def check_user_phone_access(username: str, phone_number: str):
            """Simulate the access check function from main.py"""
            mentor_row = await conn.fetchrow(
                f"SELECT mentor_id FROM {SCHEMA_NAME}.mentors WHERE username = $1", username
            )
            if not mentor_row:
                # If user doesn't exist in mentors table, they have no restrictions (full access)
                return True
            
            mentor_id = mentor_row['mentor_id']
            
            # Check if the user has access to this specific phone number
            access_row = await conn.fetchrow(
                f"SELECT access_id FROM {SCHEMA_NAME}.mentor_phone_access WHERE mentor_id = $1 AND phone_number = $2",
                mentor_id, phone_number
            )
            if access_row:
                return True
            else:
                # Check if the phone number pattern matches (using LIKE operator)
                # This allows for partial matches like '%123%' for numbers containing '123'
                access_row = await conn.fetchrow(
                    f"SELECT access_id FROM {SCHEMA_NAME}.mentor_phone_access WHERE mentor_id = $1 AND $2 LIKE phone_number",
                    mentor_id, phone_number
                )
                return access_row is not None
        
        # Test access for mentor1
        print(f"\nAccess tests for mentor1:")
        print(f"Access to +1234567890: {await check_user_phone_access('mentor1', '+1234567890')}")
        print(f"Access to +0987654321: {await check_user_phone_access('mentor1', '+0987654321')}")
        print(f"Access to +11111111: {await check_user_phone_access('mentor1', '+111111111')}")
        
        # Test access for mentor2
        print(f"\nAccess tests for mentor2:")
        print(f"Access to +111111: {await check_user_phone_access('mentor2', '+1111111111')}")
        print(f"Access to +222222: {await check_user_phone_access('mentor2', '+22222')}")
        print(f"Access to +1234567890: {await check_user_phone_access('mentor2', '+1234567890')}")
        
    finally:
        await conn.close()

async def main():
    print("Setting up test data...")
    await setup_test_data()
    print("\nTest data setup complete!")
    
    print("\nTesting access logic...")
    await test_access_logic()
    print("\nAccess logic test complete!")

if __name__ == "__main__":
    asyncio.run(main())