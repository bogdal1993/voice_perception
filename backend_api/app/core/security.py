from datetime import datetime, timedelta
from typing import Optional
import secrets
import bcrypt
import jwt
import hashlib
import asyncpg
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from pydantic import BaseModel
from ..core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class User(BaseModel):
    username: str
    role: str
    is_active: bool = True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt
    """
    return pwd_context.hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def verify_token(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Verify the JWT token and return token data
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None or role is None:
            raise credentials_exception
        
        token_data = TokenData(username=username, role=role)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception
    except jwt.exceptions.DecodeError:
        raise credentials_exception
    
    return token_data


def get_current_user(token_data: TokenData = Depends(verify_token)) -> User:
    """
    Get the current authenticated user
    """
    return User(username=token_data.username, role=token_data.role, is_active=True)


def get_current_admin_user(current_user: User = Depends(get_current_user)):
    """
    Get the current admin user, raises an exception if not an admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# API Key Functions
API_KEY_PREFIX = "vpak_"
API_KEY_LENGTH = 64  # Total length including prefix


def generate_api_key() -> str:
    """
    Generate a random API key with prefix
    Format: vpak_<64_random_hex_chars>
    """
    random_bytes = secrets.token_bytes(32)
    random_part = random_bytes.hex()
    return f"{API_KEY_PREFIX}{random_part}"


def hash_api_key(api_key: str) -> str:
    """
    Hash the API key for storage (SHA-256)
    Only hash the part after the prefix
    """
    if api_key.startswith(API_KEY_PREFIX):
        key_part = api_key[len(API_KEY_PREFIX):]
    else:
        key_part = api_key
    return hashlib.sha256(key_part.encode()).hexdigest()


def verify_api_key(plain_key: str, key_hash: str) -> bool:
    """
    Verify if the plain key matches the hashed key
    """
    if plain_key.startswith(API_KEY_PREFIX):
        key_part = plain_key[len(API_KEY_PREFIX):]
    else:
        key_part = plain_key
    computed_hash = hashlib.sha256(key_part.encode()).hexdigest()
    return secrets.compare_digest(computed_hash, key_hash)


async def get_current_user_from_api_key(
    api_key: str,
    api_key_hash: str,
    connection: asyncpg.Connection
):
    """
    Get user from API key
    """
    from ..models.api_key import ApiKey
    from ..models.user import User as UserModel
    
    # Verify API key
    if not verify_api_key(api_key, api_key_hash):
        return None
    
    # Get API key record
    api_key_record = await ApiKey.get_by_key_hash(connection, api_key_hash)
    if not api_key_record:
        return None
    
    # Get mentor/user
    user_record = await UserModel.get_by_id(connection, api_key_record.mentor_id)
    if not user_record or not user_record.is_active:
        return None
    
    # Update last used timestamp
    await api_key_record.update_last_used(connection)
    
    return User(username=user_record.username, role=user_record.role, is_active=user_record.is_active)