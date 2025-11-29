from typing import Union
import asyncpg, uuid, os
import datetime
import aiofiles, json
from fastapi.responses import FileResponse

from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks, Request, HTTPException

from fastapi.middleware.cors import CORSMiddleware

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
APIURL = os.getenv('APIURL')
class Database():
	async def create_pool(self):
		self.pool = await asyncpg.create_pool(DSN)
		#self.pool = await asyncpg.create_pool(user='voiceperception', host='192.168.0.147', password = 'voiceperception', database = 'voiceperception')
		
db = Database()
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
			schema_name = 'vp', records=data,
			columns = ['call_uuid','file_server','file_path','num_channels']
		)
		
		data = [(call_uuid,APIURL,path,'ready')]
		result = await con.copy_records_to_table(
			'transcript_queue',
			schema_name = 'vp', records=data,
			columns = ['call_uuid','file_server','file_path','status']
		)
		

@app.post("/files/")
async def create_file(
	call_start_ts: datetime.datetime = Form(),
	call_end_ts: datetime.datetime = Form(),
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
			schema_name = 'vp', records=data,
			columns = ['call_uuid','call_start_ts','call_end_ts','caller','calle','duration','direction']
		)
	return {"uuid": call_uuid}
	
@app.get("/file/{call_uuid}")
async def get_file(call_uuid: str):
	async with db.pool.acquire() as con:
		row = await con.fetchrow('SELECT file_path FROM vp.files where call_uuid = $1', call_uuid)
		return FileResponse(row['file_path'])
	
	
@app.post("/meta/{call_uuid}")
async def add_meta(call_uuid: str,request: Request):
	req_json = await request.json()
	async with db.pool.acquire() as con:
		data = [(call_uuid,json.dumps(req_json))]
		result = await con.copy_records_to_table(
			'calls_meta',
			schema_name = 'vp', records=data,
			columns = ['call_uuid','meta']
		)
		return {"result": result}
	
	