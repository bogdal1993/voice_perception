from typing import Union
import asyncpg, uuid, os
import datetime
import aiofiles, json
from fastapi.responses import FileResponse

from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks, Request, HTTPException, Depends

from fastapi.middleware.cors import CORSMiddleware

from typing import Optional

# JWT and authentication imports
import jwt
from jwt import PyJWT
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel

app = FastAPI()

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
API_KEY_PREFIX = "vpak_"

# OAuth2 scheme for token authentication
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer(auto_error=False) # auto_error=False allows optional authentication


def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    import hashlib
    if api_key.startswith(API_KEY_PREFIX):
        key_part = api_key[len(API_KEY_PREFIX):]
    else:
        key_part = api_key
    return hashlib.sha256(key_part.encode()).hexdigest()


def verify_api_key(plain_key: str, key_hash: str) -> bool:
    """Verify if plain key matches hashed key"""
    import hashlib
    if plain_key.startswith(API_KEY_PREFIX):
        key_part = plain_key[len(API_KEY_PREFIX):]
    else:
        key_part = plain_key
    computed_hash = hashlib.sha256(key_part.encode()).hexdigest()
    import secrets
    return secrets.compare_digest(computed_hash, key_hash)


async def get_user_from_api_key(credentials: str) -> dict:
    """Get user from API key"""
    import hashlib
    import secrets
    
    # Hash the provided key
    key_hash = hash_api_key(credentials)
    
    # Check if it's an API key
    if not credentials.startswith(API_KEY_PREFIX):
        return None
    
    # Query database for API key
    async with db.pool.acquire() as con:
        # Get API key record
        api_key_record = await con.fetchrow(
            f"SELECT api_key_id, mentor_id FROM {SCHEMA_NAME}.api_keys WHERE key_hash = $1",
            key_hash
        )
        
        if not api_key_record:
            return None
        
        # Update last_used_at
        await con.execute(
            f"UPDATE {SCHEMA_NAME}.api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE api_key_id = $1",
            api_key_record['api_key_id']
        )
        
        # Get mentor/user
        user = await con.fetchrow(
            f"SELECT mentor_id, username, role, is_active FROM {SCHEMA_NAME}.mentors WHERE mentor_id = $1",
            api_key_record['mentor_id']
        )
        
        if user is None or not user['is_active']:
            return None
        
        return user


# Custom dependency to optionally get user from token or API key (returns None if no auth provided)
async def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None or not credentials.credentials:
        # No authentication provided - could be internal service
        return None

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check if it's an API key
    if credentials.credentials.startswith(API_KEY_PREFIX):
        user = await get_user_from_api_key(credentials.credentials)
        if user is None:
            raise credentials_exception
        return user
    
    # Otherwise, treat as JWT token
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception
    except Exception as e:
        raise credentials_exception
    
    # Verify user exists in database
    async with db.pool.acquire() as con:
        user = await con.fetchrow(f"SELECT mentor_id, username, role, is_active FROM {SCHEMA_NAME}.mentors WHERE username = $1", token_data.username)
        if user is None or not user['is_active']:
            raise credentials_exception
    return user

DSN = os.getenv('DSN')
APIURL = os.getenv('APIURL')
SCHEMA_NAME = os.getenv('DB_SCHEMA', 'vp')  # Default to 'vp' if not specified
class Database():
	async def create_pool(self):
		self.pool = await asyncpg.create_pool(DSN)
		#self.pool = await asyncpg.create_pool(user='voiceperception', host='192.168.0.147', password = 'voiceperception', database = 'voiceperception')
		
db = Database()

# Authentication models
class TokenData(BaseModel):
    username: str = None

# Function to verify if user has access to a specific call
async def check_user_call_access(username: str, call_uuid: str, con) -> bool:
    # First check if the user is an admin
    mentor_row = await con.fetchrow(
        f"SELECT mentor_id, role FROM {SCHEMA_NAME}.mentors WHERE username = $1", username
    )
    if mentor_row and mentor_row['role'] == 'admin':
        # Admin users have access to all calls
        return True

    # Get call information
    call_info = await con.fetchrow(f'SELECT caller, calle FROM {SCHEMA_NAME}.calls WHERE call_uuid = $1', call_uuid)
    if not call_info:
        return False  # Call doesn't exist

    # Check if user has access to either the caller or callee number
    caller_access = await check_user_phone_access(username, call_info['caller'], con)
    calle_access = await check_user_phone_access(username, call_info['calle'], con)
    
    return caller_access or calle_access

# Function to check if a user has access to a specific phone number
async def check_user_phone_access(username: str, phone_number: str, con) -> bool:
    # First, check if the user exists in the mentors table
    mentor_row = await con.fetchrow(
        f"SELECT mentor_id, role FROM {SCHEMA_NAME}.mentors WHERE username = $1", username
    )
    if not mentor_row:
        # If user doesn't exist in mentors table, they have no restrictions (full access)
        return True
    
    # If user is admin, they have access to everything
    if mentor_row['role'] == 'admin':
        return True
        
    mentor_id = mentor_row['mentor_id']
    
    # Check if the user has access to this specific phone number
    access_row = await con.fetchrow(
        f"SELECT access_id FROM {SCHEMA_NAME}.mentor_phone_access WHERE mentor_id = $1 AND phone_number = $2",
        mentor_id, phone_number
    )
    if access_row:
        return True
    else:
        # Check if the phone number pattern matches (using LIKE operator)
        # This allows for partial matches like '%123%' for numbers containing '123'
        access_row = await con.fetchrow(
            f"SELECT access_id FROM {SCHEMA_NAME}.mentor_phone_access WHERE mentor_id = $1 AND $2 LIKE phone_number",
            mentor_id, phone_number
        )
        return access_row is not None

# Dependency to get current user from token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise credentials_exception
    except Exception as e:
        raise credentials_exception
    
    # Verify user exists in database
    async with db.pool.acquire() as con:
        user = await con.fetchrow(f"SELECT mentor_id, username, role, is_active FROM {SCHEMA_NAME}.mentors WHERE username = $1", token_data.username)
        if user is None or not user['is_active']:
            raise credentials_exception
    return user
#app.include_router(prefix="/importapi")

base_path = "./media"

		
def generate_uuid():
	return str(uuid.uuid4())
		
@app.on_event("startup")
async def startup():
	await db.create_pool()
		
async def save_file_to_path(path,file,call_uuid):
	async with aiofiles.open(path, 'wb') as out_file:
	
		content = await file.read()
		await out_file.write(content)
		
	async with db.pool.acquire() as con:
		data = [(call_uuid,APIURL,path,1)]
		result = await con.copy_records_to_table(
			'files',
			schema_name = SCHEMA_NAME, records=data,
			columns = ['call_uuid','file_server','file_path','num_channels']
		)
		
		data = [(call_uuid,APIURL,path,'ready')]
		result = await con.copy_records_to_table(
			'transcript_queue',
			schema_name = SCHEMA_NAME, records=data,
			columns = ['call_uuid','file_server','file_path','status']
		)
		

@app.post("/files/")
async def create_file(
	call_start_ts: datetime = Form(),
	call_end_ts: datetime = Form(),
	caller: str = Form(),
	calle: str = Form(),
	direction: str = Form(),
	duration: int = Form(),
	save_file: bool  = Form(False), 
	media: UploadFile = File(),
	background_tasks: BackgroundTasks = BackgroundTasks()
	):
	if not direction in ['inbound','outbound','local']:
		raise HTTPException(status_code=422, detail="Incorrect direction") 
	call_uuid = generate_uuid()
	if save_file:
		path = os.path.join(base_path,media.filename)
		background_tasks.add_task(save_file_to_path, path, media,call_uuid )
	async with db.pool.acquire() as con:
		data = [(call_uuid,call_start_ts,call_end_ts,caller,calle,duration,direction)]
		result = await con.copy_records_to_table(
			'calls',
			schema_name = SCHEMA_NAME, records=data,
			columns = ['call_uuid','call_start_ts','call_end_ts','caller','calle','duration','direction']
		)
	return {"uuid": call_uuid}
	
@app.get("/file/{call_uuid}")
async def get_file(call_uuid: str, request: Request, current_user: dict = Depends(get_current_user_optional)):
    async with db.pool.acquire() as con:
        # If user is authenticated, check permissions
        if current_user is not None:
            # Check if user is an admin
            is_admin = current_user['role'] == 'admin'
            
            # Check if user has access to this call (for non-admin users)
            if not is_admin:
                has_access = await check_user_call_access(current_user['username'], call_uuid, con)
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied to this call")
        else:
            # No authentication provided - could be internal service like transcript server
            # For security, we should still check if the call exists
            # Optionally, we could check if the request is coming from a local/internal IP
            call_info = await con.fetchrow(f'SELECT call_uuid FROM {SCHEMA_NAME}.calls WHERE call_uuid = $1', call_uuid)
            if not call_info:
                raise HTTPException(status_code=404, detail="Call not found")
        
        row = await con.fetchrow(f'SELECT file_path FROM {SCHEMA_NAME}.files where call_uuid = $1', call_uuid)
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(row['file_path'])
	
	
@app.post("/meta/{call_uuid}")
async def add_meta(call_uuid: str,request: Request):
	req_json = await request.json()
	async with db.pool.acquire() as con:
		data = [(call_uuid,json.dumps(req_json))]
		result = await con.copy_records_to_table(
			'calls_meta',
			schema_name = SCHEMA_NAME, records=data,
			columns = ['call_uuid','meta']
		)
		return {"result": result}
	
	