# Voice Perception Backend API Documentation

## Overview

This API provides functionality for voice perception and call analytics. It includes features for user management, call data retrieval, statistics, and tagging.

## Table of Contents

1. [Authentication](#authentication)
2. [User Management](#user-management)
3. [Call Data](#call-data)
4. [Statistics](#statistics)
5. [Mentor Management](#mentor-management)
6. [Tags](#tags)

## Authentication

The API uses JWT tokens for authentication. To access protected endpoints, you must include the token in the Authorization header.

### Get Token

**Endpoint:** `POST /auth/token`

**Description:** Authenticate and get a JWT token.

**Request:**
```
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

## User Management

### Create User (Admin Only)

**Endpoint:** `POST /auth/users/`

**Description:** Create a new user (admin access required).

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "username": "newuser",
  "password": "password123",
  "role": "user"
}
```

**Response:**
```json
{
 "user_id": 123,
  "username": "newuser",
  "role": "user",
  "created_at": "2023-01-01T00:00:00",
  "is_active": true
}
```

### Get All Users (Admin Only)

**Endpoint:** `GET /auth/users/`

**Description:** Get a list of all users (admin access required).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "user_id": 1,
    "username": "admin",
    "role": "admin",
    "created_at": "2023-01-01T00:00:00",
    "is_active": true
  }
]
```

### Delete User (Admin Only)

**Endpoint:** `DELETE /auth/users/{user_id}`

**Description:** Delete a user by ID (admin access required).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "User deleted successfully"
}
```

## Call Data

### Get Call Transcript

**Endpoint:** `GET /calls/call_transcript/{call_uuid}`

**Description:** Get the transcript for a specific call.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "spk": "0",
    "start": 0.0,
    "end": 2.5,
    "text": "Hello, how are you?",
    "emotion": "neutral"
  }
]
```

### Get Call Tags

**Endpoint:** `GET /calls/call_tags/{call_uuid}`

**Description:** Get tags for a specific call.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "tag": "greeting",
    "spk": "0",
    "start": 0.0,
    "end": 2.5
  }
]
```

### Get Calls

**Endpoint:** `POST /calls/calls/`

**Description:** Get calls based on filters.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "limit": 10,
  "offset": 0,
  "startDate": "2023-01-01T00:00:00",
  "endDate": "2023-12-31T23:59:59",
  "caller": "%",
  "callee": "%"
}
```

**Response:**
```json
[
  {
    "call_uuid": "uuid-string",
    "call_start_ts": "2023-01-01T10:00:00",
    "caller": "1234567890",
    "calle": "0987654321",
    "duration": 300,
    "direction": "inbound"
  }
]
```

### Search Calls by Text

**Endpoint:** `POST /calls/textsearch/`

**Description:** Search calls by text content.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "limit": 10,
  "offset": 0,
  "startDate": "2023-01-01T00:00:00",
  "endDate": "2023-12-31T23:59:59",
  "caller": "%",
  "callee": "%",
  "words1": [{"value": "hello"}],
  "words2": [{"value": "world"}]
}
```

**Response:**
```json
[
  {
    "call_uuid": "uuid-string",
    "call_start_ts": "2023-01-01T10:00:00",
    "caller": "1234567890",
    "calle": "0987654321",
    "duration": 300,
    "direction": "inbound",
    "text": "Hello, world!"
  }
]
```

## Statistics

### Get Emotion Statistics

**Endpoint:** `POST /calls/stats/emotions`

**Description:** Get emotion statistics for calls.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "startDate": "2023-01-01T00:00",
  "endDate": "2023-12-31T23:59:59",
  "caller": "%",
  "callee": "%",
  "spk": "0"
}
```

**Response:**
```json
[
  {
    "label": "neutral",
    "value": 150
  },
  {
    "label": "positive",
    "value": 80
  }
]
```

### Get Top Words Statistics

**Endpoint:** `POST /calls/stats/topwords`

**Description:** Get top word statistics for calls.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "startDate": "2023-01-01T00:00:00",
  "endDate": "2023-12-31T23:59:59",
  "caller": "%",
  "callee": "%",
  "spk": "0",
  "limit": 10,
  "part": ["noun", "verb"]
}
```

**Response:**
```json
[
  {
    "label": "hello",
    "value": 120
  },
  {
    "label": "world",
    "value": 95
 }
]
```

### Get Call Count Statistics

**Endpoint:** `POST /calls/stats/counts`

**Description:** Get call count statistics.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "startDate": "2023-01-01T00:00:00",
  "endDate": "2023-12-31T23:59:59",
  "caller": "%",
  "callee": "%",
  "sampling": "day"
}
```

**Response:**
```json
[
  {
    "label": "2023-01-01T00:00:00",
    "value": 50
 }
]
```

### Get Call Statistics

**Endpoint:** `POST /calls/calls/stats`

**Description:** Get overall call statistics.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "startDate": "2023-01-01T00:00",
  "endDate": "2023-12-31T23:59",
  "caller": "%",
  "callee": "%"
}
```

**Response:**
```json
{
  "incoming": {
    "count": 120,
    "total_duration": 36000
  },
  "outgoing": {
    "count": 80,
    "total_duration": 24000
  },
  "total": {
    "count": 200,
    "total_duration": 60000
  }
}
```

## Mentor Management

### Create Mentor (Admin Only)

**Endpoint:** `POST /mentors/mentors/`

**Description:** Create a new mentor (admin access required).

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "username": "mentor1"
}
```

**Response:**
```json
{
  "mentor_id": 1,
  "username": "mentor1",
  "created_at": "2023-01-01T00:00:00"
}
```

### Get All Mentors (Admin Only)

**Endpoint:** `GET /mentors/mentors/`

**Description:** Get all mentors (admin access required).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "mentor_id": 1,
    "username": "mentor1",
    "created_at": "2023-01-01T00:00"
  }
]
```

### Add Phone Access to Mentor (Admin Only)

**Endpoint:** `POST /mentors/mentors/{mentor_id}/phone-access/`

**Description:** Add phone access for a mentor (admin access required).

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "phone_number": "1234567890"
}
```

**Response:**
```json
{
  "access_id": 1,
  "mentor_id": 1,
  "phone_number": "1234567890",
 "created_at": "2023-01-01T00:00"
}
```

### Get Mentors with Access (Admin Only)

**Endpoint:** `GET /mentors/mentors/with-access/`

**Description:** Get all mentors with their phone access (admin access required).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "mentor_id": 1,
    "username": "mentor1",
    "created_at": "2023-01-01T00:00",
    "phone_access": [
      {
        "access_id": 1,
        "phone_number": "1234567890",
        "created_at": "2023-01-01T00:00:00"
      }
    ]
  }
]
```

## Tags

### Get All Tags (Admin Only)

**Endpoint:** `GET /tags/tags/`

**Description:** Get all tags (admin access required).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "tag_id": 1,
    "tag_name": "greeting",
    "tag_spk": "0",
    "tag_texts": ["hello", "hi", "good morning"]
  }
]
```

### Create Tag (Admin Only)

**Endpoint:** `POST /tags/tag/`

**Description:** Create a new tag (admin access required).

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "tag_id": 0,
  "tag_name": "greeting",
  "tag_spk": "0",
  "tag_texts": ["hello", "hi", "good morning"]
}
```

**Response:**
```json
{
  "message": "Тег успешно создан",
  "row": {
    "tag_id": 2
  }
}
```

### Update Tag (Admin Only)

**Endpoint:** `PUT /tags/tag/{tag_id}`

**Description:** Update a tag (admin access required).

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "tag_id": 1,
  "tag_name": "greeting",
  "tag_spk": "0",
  "tag_texts": ["hello", "hi", "good morning", "good day"]
}
```

**Response:**
```json
{
  "message": "Тег 1 успешно сохранен"
}
```

### Delete Tag (Admin Only)

**Endpoint:** `DELETE /tags/tag/{tag_id}`

**Description:** Delete a tag (admin access required).

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "message": "Тег успешно удален"
}
```

## Error Handling

The API returns appropriate HTTP status codes:

- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

## Security

- All sensitive endpoints require JWT authentication
- Admin-only endpoints require admin role
- Passwords are hashed using bcrypt
- SQL injection is prevented through parameterized queries
- Access control is implemented based on mentor phone access permissions