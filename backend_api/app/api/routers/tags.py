import json
from fastapi import APIRouter, Depends, HTTPException, status

from ...core.security import get_current_admin_user
from ...database.connection import db
from ...schemas.call import TagItem
from ...core.config import settings

router = APIRouter()


async def update_tag(tag_id: int, updated_tag: TagItem):
    """Update a tag by ID"""
    async with db.pool.acquire() as connection:
        await connection.execute(
            f"UPDATE {settings.DB_SCHEMA}.tags_core SET tag_texts = $1, tag_spk = $2, tag_name = $3 WHERE tag_id = $4",
            json.dumps(updated_tag.tag_texts), 
            int(updated_tag.tag_spk), 
            updated_tag.tag_name, 
            tag_id
        )


async def create_new_tag(new_tag: TagItem):
    """Create a new tag"""
    async with db.pool.acquire() as connection:
        row = await connection.fetch(
            f"INSERT into {settings.DB_SCHEMA}.tags_core(tag_name, tag_spk, tag_texts) values($1,$2,$3) returning tag_id",
            new_tag.tag_name, 
            int(new_tag.tag_spk), 
            json.dumps(new_tag.tag_texts)
        )
        return row[0]


async def delete_tag_by_id(tag_id: int):
    """Delete a tag by ID"""
    async with db.pool.acquire() as connection:
        await connection.execute(
            f"delete from {settings.DB_SCHEMA}.tags_core WHERE tag_id = $1", 
            tag_id
        )


@router.get("/tags/")
async def get_tags_list(current_user=Depends(get_current_admin_user)):
    """
    Get all tags (admin only)
    """
    async with db.pool.acquire() as connection:
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        row = await connection.fetch(f"SELECT tag_id, tag_name, tag_spk, tag_texts::json FROM {settings.DB_SCHEMA}.tags_core order by tag_id")
        return row


@router.put("/tag/{tag_id}")
async def save_tag(
    tag_id: int, 
    updated_tag: TagItem, 
    current_user=Depends(get_current_admin_user)
):
    """
    Update a tag (admin only)
    """
    await update_tag(tag_id, updated_tag)
    return {"message": f"Тег {tag_id} успешно сохранен"}


@router.post("/tag/")
async def create_tag(
    new_tag: TagItem, 
    current_user=Depends(get_current_admin_user)
):
    """
    Create a new tag (admin only)
    """
    row = await create_new_tag(new_tag)
    return {"message": f"Тег успешно создан", "row": row}


@router.delete("/tag/{tag_id}")
async def delete_tag(
    tag_id: int, 
    current_user=Depends(get_current_admin_user)
):
    """
    Delete a tag (admin only)
    """
    await delete_tag_by_id(tag_id)
    return {"message": f"Тег успешно удален"}