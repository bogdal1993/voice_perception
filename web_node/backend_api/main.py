from typing import Union
import asyncpg, uuid, os
import datetime
import aiofiles, json
from datetime import datetime
from fastapi.responses import FileResponse
from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks, Request, HTTPException,Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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

class callFilters(BaseModel):
    limit: int
    offset: int
    startDate: datetime
    endDate: datetime
    caller: str = '%'
    callee: str = '%'
    
class callFiltersWord(BaseModel):
    limit: int
    offset: int
    startDate: datetime
    endDate: datetime
    caller: str = '%'
    callee: str = '%'
    words1: list = [{'value':'%'}]
    words2: list = [{'value':'%'}]
    
class statFilters(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str
    callee: str
    spk: str
    
class statFiltersWords(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str
    callee: str
    spk: str
    limit: int
    part: list = []
    
class statFiltersCount(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str
    callee: str
    sampling: str = 'day'
    
class TagItem(BaseModel):
    tag_id: int
    tag_name: str
    tag_spk: int
    tag_texts: List[str]
    

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
        
@app.get("/call_tags/{call_uuid}")
async def get_call_tags(call_uuid: str):
    async with db.pool.acquire() as con:
        row = await con.fetchrow('SELECT tags_json FROM vp.calls_tags where call_uuid = $1', call_uuid)
        return json.loads(row['tags_json'])
        
        
@app.post("/stats/emotions")
async def get_stats_emotions(statFilters: statFilters):
    emo_color={'negative':'#fa5e66', 'neutral':'#5ea7fa', 'positive':'#5efa8d', 'skip':'#a8a8a8', 'speech':'#eeeeee'}
    data = {"labels":[],"datasets":[{"label":"Число фраз","data":[],"backgroundColor":[]}]}
    async with db.pool.acquire() as con:
        row = await con.fetch("""SELECT  arr.transcription ->> 'emotion' as label,
        count(arr.call_uuid) as value
            FROM vp.calls_transcription t,
        jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid) 
            where t.call_uuid in (
                SELECT call_uuid
                FROM vp.calls
                where caller like ($3)
                and calle like ($4)
                and call_start_ts between $1 and $2
            )
            and arr.transcription ->> 'spk' = $5
            group by label
            order by label""",
        statFilters.startDate,
        statFilters.endDate,
        statFilters.caller,
        statFilters.callee,
        statFilters.spk)
        '''for emo in row:
            data['labels'].append(emo['emotion'])
            data['datasets'][0]['data'].append(emo['count'])
            data['datasets'][0]['backgroundColor'].append(emo_color[emo['emotion']])'''
        return row
        
@app.post("/stats/topwords")
async def get_stats_topwords(statFilters: statFiltersWords):
    async with db.pool.acquire() as con:
        row = await con.fetch("""SELECT  w.resul ->> 'lemma' as "label",
count(w.call_uuid) as "value"
    FROM vp.calls_transcription t,
jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid),
jsonb_array_elements(arr.transcription -> 'result') with ordinality w(resul, call_uuid)
            where t.call_uuid in (
                SELECT call_uuid
                FROM vp.calls
                where caller like ($3)
                and calle like ($4)
                and call_start_ts between $1 and $2
            )
            and arr.transcription ->> 'spk' = $5
            and w.resul ->> 'part' = any($7::varchar[])
            group by "label"
            order by "value" desc
            limit $6""",
        statFilters.startDate,
        statFilters.endDate,
        statFilters.caller,
        statFilters.callee,
        statFilters.spk,
        statFilters.limit,
        statFilters.part)
        return row
        
@app.post("/stats/counts")
async def get_stats_counts(statFilters: statFiltersCount):
    async with db.pool.acquire() as con:
        row = await con.fetch("""
            SELECT date_trunc($5, call_start_ts) as "label",
            count(*) as "value"
            FROM vp.calls
            where caller like ($3)
            and calle like ($4)
            and call_start_ts between $1 and $2
            group by 1
            ORDER BY 1""",
        statFilters.startDate,
        statFilters.endDate,
        statFilters.caller,
        statFilters.callee,
        statFilters.sampling)
        return row    

@app.post("/stats/tagscount")
async def get_stats_tagscount(statFilters: statFilters):
    async with db.pool.acquire() as con:
        row = await con.fetch("""SELECT  arr.tags_json ->> 'tag' as label,
        count(arr.call_uuid) as value
            FROM vp.calls_tags t,
        jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid) 
            where t.call_uuid in (
                SELECT call_uuid
                FROM vp.calls
                where caller like ($3)
                and calle like ($4)
                and call_start_ts between $1 and $2
            )
            and arr.tags_json ->> 'spk' = $5
            group by label
            order by label""",
        statFilters.startDate,
        statFilters.endDate,
        statFilters.caller,
        statFilters.callee,
        statFilters.spk)
        return row
		
@app.post("/stats/tagspercent")
async def get_stats_tagspercent(statFilters: statFilters):
    async with db.pool.acquire() as con:
        row = await con.fetch("""(SELECT 
    arr.tags_json ->> 'tag' as label,        
    count(arr.call_uuid)::numeric/ (SELECT COUNT(*) FROM vp.calls 
        WHERE caller LIKE ($3) 
        AND calle LIKE ($4) 
        AND call_start_ts BETWEEN $1 and $2
    )*100 as value
FROM 
    vp.calls_tags t,        
    jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid) 
WHERE 
    t.call_uuid IN (
        SELECT call_uuid
        FROM vp.calls                
        WHERE caller LIKE ($3)
        AND calle LIKE ($4)                
        AND call_start_ts BETWEEN $1 and $2
    )            
    AND arr.tags_json ->> 'spk' = $5
GROUP BY 
    label            
ORDER BY 
    label)
union all
select 'ALL', 100""",
        statFilters.startDate,
        statFilters.endDate,
        statFilters.caller,
        statFilters.callee,
        statFilters.spk)
        return row		

@app.post("/calls/")
async def get_calls(callFilter: callFilters):
    async with db.pool.acquire() as con:
        row = await con.fetch("""SELECT call_uuid, call_start_ts, caller, calle, duration, direction 
        FROM vp.calls 
        WHERE call_start_ts BETWEEN $4 and $3 
        and caller like ($5)
        and calle like ($6)
        order by call_end_ts desc limit $1 offset $2""",
        callFilter.limit,
        callFilter.offset,
        callFilter.startDate,
        callFilter.endDate,
        callFilter.caller,
        callFilter.callee)
        return row
        
def format_filter_transcription(words1,words2):
    if words1:
        return "and arr.transcription ->> 'spk' = '0' and arr.transcription ->> 'text' like any(ARRAY[{}])".format(','.join(words1))
    if words2:
        return "and arr.transcription ->> 'spk' = '1' and arr.transcription ->> 'text' like any(ARRAY[{}])".format(','.join(words2))
        
    
@app.post("/textsearch/")
async def get_calls(callFilter: callFiltersWord):
    callFilter.words1 = ["'%"+x['value']+"%'" for x in callFilter.words1]
    callFilter.words2 = ["'%"+x['value']+"%'" for x in callFilter.words2]
    formatted_transcription_filter = format_filter_transcription(callFilter.words1,callFilter.words2)
    async with db.pool.acquire() as con:
        row = await con.fetch("""SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction,
arr.transcription ->> 'text' as text
            FROM vp.calls_transcription t,
        jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid) 
        ,vp.calls c
            where t.call_uuid in (
                SELECT call_uuid
                FROM vp.calls
                where caller like ($5)
                and calle like ($6)
                and call_start_ts between $3 and $4
            )
            and c.call_uuid = t.call_uuid
            {}
        order by c.call_end_ts desc limit $1 offset $2""".format(formatted_transcription_filter),
        callFilter.limit,
        callFilter.offset,
        callFilter.startDate,
        callFilter.endDate,
        callFilter.caller,
        callFilter.callee)
        return row    


async def update_tag(tag_id: int, updated_tag: TagItem):
    async with db.pool.acquire() as connection:
        await connection.execute(
            "UPDATE vp.tags_core SET tag_texts = $1, tag_spk = $2, tag_name = $3 WHERE tag_id = $4",
            json.dumps(updated_tag.tag_texts), updated_tag.tag_spk, updated_tag.tag_name, tag_id
        )
        
async def create_new_tag(new_tag: TagItem):
    async with db.pool.acquire() as connection:
        row = await connection.fetch(
            "INSERT into vp.tags_core(tag_name, tag_spk, tag_texts) values($1,$2,$3) returning tag_id",
            new_tag.tag_name,new_tag.tag_spk,json.dumps(new_tag.tag_texts)
        )
        return row[0]
		
async def delete_tag_by_id(tag_id: int):
    async with db.pool.acquire() as connection:
        await connection.execute(
            "delete from vp.tags_core WHERE tag_id = $1", tag_id
        )
		

@app.get("/tags")
async def get_tags_list():
    async with db.pool.acquire() as con:
        await con.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        row = await con.fetch("SELECT tag_id, tag_name, tag_spk, tag_texts::json FROM vp.tags_core order by tag_id")
        return row
        
@app.put("/tag/{tag_id}")
async def save_tag(tag_id: int, updated_tag: TagItem):
    await update_tag(tag_id, updated_tag)
    return {"message": f"Тег {tag_id} успешно сохранен"}
    
@app.post("/tag")
async def create_tag(new_tag: TagItem):
    row = await create_new_tag(new_tag)
    return {"message": f"Тег успешно создан","row":row}
	
@app.delete("/tag/{tag_id}")
async def delete_tag(tag_id: int):
    row = await delete_tag_by_id(tag_id)
    return {"message": f"Тег успешно удален"}