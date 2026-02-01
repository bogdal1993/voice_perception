#!/usr/bin/env python
"""
Test script to verify mentor management functionality
"""
import requests
import json
import os

# Configuration
BASE_URL = "http://localhost:8001"
# You need to provide a valid admin authentication token
AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN", "your_admin_token_here")

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}

def test_mentor_management():
    print("Testing Mentor Management Functionality")
    print("=" * 50)
    
    # Test 1: Create a mentor
    print("\n1. Creating a mentor...")
    mentor_data = {"username": "test_mentor"}
    response = requests.post(f"{BASE_URL}/mentors/", json=mentor_data, headers=HEADERS)
    if response.status_code == 200:
        mentor = response.json()
        mentor_id = mentor['mentor_id']
        print(f"✓ Mentor created successfully: ID {mentor_id}, Username {mentor['username']}")
    else:
        print(f"✗ Failed to create mentor: {response.status_code} - {response.text}")
        return False
    
    # Test 2: Get all mentors
    print("\n2. Getting all mentors...")
    response = requests.get(f"{BASE_URL}/mentors/", headers=HEADERS)
    if response.status_code == 200:
        mentors = response.json()
        print(f"✓ Retrieved {len(mentors)} mentors")
        print(f"Mentors: {mentors}")
    else:
        print(f"✗ Failed to get mentors: {response.status_code} - {response.text}")
        return False
    
    # Test 3: Add phone access for the mentor
    print("\n3. Adding phone access for mentor...")
    phone_access_data = {"phone_number": "+1234567890"}
    response = requests.post(f"{BASE_URL}/mentors/{mentor_id}/phone-access/", 
                            json=phone_access_data, headers=HEADERS)
    if response.status_code == 200:
        phone_access = response.json()
        access_id = phone_access['access_id']
        print(f"✓ Phone access added: ID {access_id}, Phone {phone_access['phone_number']}")
    else:
        print(f"✗ Failed to add phone access: {response.status_code} - {response.text}")
        return False
    
    # Test 4: Get mentor with access
    print("\n4. Getting mentors with access...")
    response = requests.get(f"{BASE_URL}/mentors/with-access/", headers=HEADERS)
    if response.status_code == 200:
        mentors_with_access = response.json()
        print(f"✓ Retrieved {len(mentors_with_access)} mentors with access")
        print(f"Mentors with access: {json.dumps(mentors_with_access, indent=2)}")
    else:
        print(f"✗ Failed to get mentors with access: {response.status_code} - {response.text}")
        return False
    
    # Test 5: Delete phone access
    print("\n5. Deleting phone access...")
    response = requests.delete(f"{BASE_URL}/mentors/{mentor_id}/phone-access/{access_id}", headers=HEADERS)
    if response.status_code == 200:
        print("✓ Phone access deleted successfully")
    else:
        print(f"✗ Failed to delete phone access: {response.status_code} - {response.text}")
        return False
    
    # Test 6: Delete mentor
    print("\n6. Deleting mentor...")
    response = requests.delete(f"{BASE_URL}/mentors/{mentor_id}", headers=HEADERS)
    if response.status_code == 200:
        print("✓ Mentor deleted successfully")
    else:
        print(f"✗ Failed to delete mentor: {response.status_code} - {response.text}")
        return False
    
    print("\n✓ All tests passed! Mentor management functionality is working correctly.")
    return True

def test_endpoints_without_auth():
    print("\nTesting endpoints without authentication...")
    print("-" * 40)
    
    # Test without auth
    response = requests.get(f"{BASE_URL}/mentors/")
    if response.status_code == 401:
        print("✓ Authentication required for /mentors/ endpoint")
    else:
        print(f"✗ Authentication not enforced: {response.status_code}")
    
    response = requests.post(f"{BASE_URL}/mentors/", json={"username": "test"})
    if response.status_code == 401:
        print("✓ Authentication required for POST /mentors/ endpoint")
    else:
        print(f"✗ Authentication not enforced: {response.status_code}")

if __name__ == "__main__":
    # Test endpoints without authentication first
    test_endpoints_without_auth()
    
    # Only run full tests if we have an auth token
    if AUTH_TOKEN != "your_admin_token_here":
        test_mentor_management()
    else:
        print("\nNote: To run full tests, please set the ADMIN_AUTH_TOKEN environment variable.")
        print("Example: export ADMIN_AUTH_TOKEN=your_token_here")