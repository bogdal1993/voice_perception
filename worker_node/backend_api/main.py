from typing import Union
import asyncpg, uuid, os
import datetime
import aiofiles, json
from fastapi.responses import FileResponse
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks, Request, HTTPException,Depends
from fastapi.middleware.cors import CORSMiddleware
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



DSN = os.getenv('DSN')
class Database():
	async def create_pool(self):
		self.pool = await asyncpg.create_pool(DSN)
		
db = Database()
#app.include_router(prefix="/backendapi")

@app.on_event("startup")
async def startup():
	await db.create_pool()
	
@app.get("/call_transcript/{call_uuid}")
async def get_call_transcript(call_uuid: str):
	async with db.pool.acquire() as con:
		row = await con.fetchrow('SELECT transcription FROM vp.calls_transcription where call_uuid = $1', call_uuid)
		return json.loads(row['transcription'])
		
		
class callFilters(BaseModel):
    limit: int
    offset: int
		
@app.post("/calls/")
async def get_calls(callFilter: callFilters):
	async with db.pool.acquire() as con:
		row = await con.fetch('SELECT * FROM vp.calls order by call_end_ts desc limit $1 offset $2',callFilter.limit,callFilter.offset)
		return row