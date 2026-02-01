from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

from ...core.security import verify_token
from ...database.connection import db
from ...schemas.call import CallFilter, CallFilterWord, StatFilter, StatFilterWords, StatFilterCount, CallStatsFilter
from ...utils.access_control import get_user_accessible_phones, check_user_phone_access
from ...core.config import settings
from ...utils.validation import (
    CallFilterValidator,
    CallFilterWordValidator,
    StatFilterValidator,
    StatFilterWordsValidator,
    StatFilterCountValidator,
    CallStatsFilterValidator
)

router = APIRouter()


def format_filter_transcription(words1: List[str], words2: List[str]) -> str:
    """Format transcription filter for queries"""
    if words1:
        return f"and arr.transcription ->> 'spk' = '0' and arr.transcription ->> 'text' like any(ARRAY[{','.join(words1)}])"
    if words2:
        return f"and arr.transcription ->> 'spk' = '1' and arr.transcription ->> 'text' like any(ARRAY[{','.join(words2)}])"
    return ""


@router.get("/call_transcript/{call_uuid}")
async def get_call_transcript(
    call_uuid: str, 
    token_data: dict = Depends(verify_token)
):
    """
    Get transcript for a specific call
    """
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if not is_admin:
            # Non-admin users - check if the call belongs to a phone number they have access to
            call_info = await connection.fetchrow(
                f'SELECT caller, calle FROM {settings.DB_SCHEMA}.calls WHERE call_uuid = $1', 
                call_uuid
            )
            if not call_info:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
            
            # Check access for both caller and calle
            caller_access = await check_user_phone_access(connection, token_data.username, call_info['caller'])
            calle_access = await check_user_phone_access(connection, token_data.username, call_info['calle'])
            
            if not caller_access and not calle_access:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this call")
                
        row = await connection.fetchrow(
            f'SELECT transcription FROM {settings.DB_SCHEMA}.calls_transcription where call_uuid = $1', 
            call_uuid
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcription not found")
        
        import json
        return json.loads(row['transcription'])


@router.get("/call_tags/{call_uuid}")
async def get_call_tags(
    call_uuid: str, 
    token_data: dict = Depends(verify_token)
):
    """
    Get tags for a specific call
    """
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if not is_admin:
            # Non-admin users - check if the call belongs to a phone number they have access to
            call_info = await connection.fetchrow(
                f'SELECT caller, calle FROM {settings.DB_SCHEMA}.calls WHERE call_uuid = $1', 
                call_uuid
            )
            if not call_info:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
            
            # Check access for both caller and calle
            caller_access = await check_user_phone_access(connection, token_data.username, call_info['caller'])
            calle_access = await check_user_phone_access(connection, token_data.username, call_info['calle'])
            
            if not caller_access and not calle_access:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this call")
                
        row = await connection.fetchrow(
            f'SELECT tags_json FROM {settings.DB_SCHEMA}.calls_tags where call_uuid = $1', 
            call_uuid
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tags not found")
        
        import json
        return json.loads(row['tags_json'])


@router.post("/stats/emotions")
async def get_stats_emotions(
    stat_filters: StatFilter, 
    token_data: dict = Depends(verify_token)
):
    """
    Get emotion statistics for calls
    """
    # Validate the input
    validator = StatFilterValidator(
        startDate=stat_filters.startDate,
        endDate=stat_filters.endDate,
        caller=stat_filters.caller,
        callee=stat_filters.callee,
        spk=stat_filters.spk
    )
    validator.validate_date_range()
    
    emo_color = {'negative': '#fa5e6', 'neutral': '#5ea7fa', 'positive': '#5efa8d', 'skip': '#a8a8a8', 'speech': '#eeeeee'}
    data = {"labels": [], "datasets": [{"label": "Число фраз", "data": [], "backgroundColor": []}]}
    
    async with db.pool.acquire() as connection:
        # Get user's accessible phone numbers
        accessible_phones = await get_user_accessible_phones(connection, token_data.username)
        if not accessible_phones:
            # If user has no accessible phones, return empty result
            return []
        
        # Construct the query with access control
        if '%' in accessible_phones:
            # User has full access
            query = f"""
            SELECT  arr.transcription ->> 'emotion' as label,
            count(arr.call_uuid) as value
                FROM {settings.DB_SCHEMA}.calls_transcription t,
            jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid)
                where t.call_uuid in (
                    SELECT call_uuid
                    FROM {settings.DB_SCHEMA}.calls
                    where caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                )
                and arr.transcription ->> 'spk' = $5
                group by label
                order by label
            """
            row = await connection.fetch(
                query,
                stat_filters.startDate,
                stat_filters.endDate,
                stat_filters.caller,
                stat_filters.callee,
                stat_filters.spk
            )
        else:
            # User has restricted access - filter by accessible phones
            phone_placeholders = ','.join([f'${i}' for i in range(6, 6+len(accessible_phones))])
            query = f"""
            SELECT  arr.transcription ->> 'emotion' as label,
            count(arr.call_uuid) as value
                FROM {settings.DB_SCHEMA}.calls_transcription t,
            jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid)
                where t.call_uuid in (
                    SELECT call_uuid
                    FROM {settings.DB_SCHEMA}.calls
                    where (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
                    and caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                )
                and arr.transcription ->> 'spk' = $5
                group by label
                order by label
            """
            
            all_params = [stat_filters.startDate, stat_filters.endDate, stat_filters.caller, stat_filters.callee, stat_filters.spk] + accessible_phones
            row = await connection.fetch(query, *all_params)
        return row


@router.post("/stats/topwords")
async def get_stats_topwords(
    stat_filters: StatFilterWords, 
    token_data: dict = Depends(verify_token)
):
    """
    Get top word statistics for calls
    """
    # Validate the input
    validator = StatFilterWordsValidator(
        startDate=stat_filters.startDate,
        endDate=stat_filters.endDate,
        caller=stat_filters.caller,
        callee=stat_filters.callee,
        spk=stat_filters.spk,
        limit=stat_filters.limit,
        part=stat_filters.part
    )
    validator.validate_date_range()
    
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if is_admin:
            # Admin users can see stats for all calls without phone restrictions
            query = f"""
            SELECT w.resul ->> 'lemma' as "label",
    count(w.call_uuid) as "value"
        FROM {settings.DB_SCHEMA}.calls_transcription t,
    jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid),
    jsonb_array_elements(arr.transcription -> 'result') with ordinality w(resul, call_uuid)
            where t.call_uuid in (
                SELECT call_uuid
                FROM {settings.DB_SCHEMA}.calls
                where caller like ($3)
                and calle like ($4)
                and call_start_ts between $1 and $2
            )
            and arr.transcription ->> 'spk' = $5
            and w.resul ->> 'part' = any($7::varchar[])
            group by "label"
            order by "value" desc
            limit $6
            """
            row = await connection.fetch(
                query,
                stat_filters.startDate,
                stat_filters.endDate,
                stat_filters.caller,
                stat_filters.callee,
                stat_filters.spk,
                stat_filters.limit,
                stat_filters.part
            )
            return row
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result
                return []
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""
                SELECT w.resul ->> 'lemma' as "label",
        count(w.call_uuid) as "value"
            FROM {settings.DB_SCHEMA}.calls_transcription t,
        jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid),
        jsonb_array_elements(arr.transcription -> 'result') with ordinality w(resul, call_uuid)
                where t.call_uuid in (
                    SELECT call_uuid
                    FROM {settings.DB_SCHEMA}.calls
                    where caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                )
                and arr.transcription ->> 'spk' = $5
                and w.resul ->> 'part' = any($7::varchar[])
                group by "label"
                order by "value" desc
                limit $6
                """
                row = await connection.fetch(
                    query,
                    stat_filters.startDate,
                    stat_filters.endDate,
                    stat_filters.caller,
                    stat_filters.callee,
                    stat_filters.spk,
                    stat_filters.limit,
                    stat_filters.part
                )
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(8, 8+len(accessible_phones))])
                query = f"""
                SELECT  w.resul ->> 'lemma' as "label",
        count(w.call_uuid) as "value"
            FROM {settings.DB_SCHEMA}.calls_transcription t,
        jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid),
        jsonb_array_elements(arr.transcription -> 'result') with ordinality w(resul, call_uuid)
                where t.call_uuid in (
                    SELECT call_uuid
                    FROM {settings.DB_SCHEMA}.calls
                    where (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
                    and caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                )
                and arr.transcription ->> 'spk' = $5
                and w.resul ->> 'part' = any($7::varchar[])
                group by "label"
                order by "value" desc
                limit $6
                """
                
                all_params = [
                    stat_filters.startDate, 
                    stat_filters.endDate, 
                    stat_filters.caller, 
                    stat_filters.callee, 
                    stat_filters.spk, 
                    stat_filters.limit, 
                    stat_filters.part
                ] + accessible_phones
                row = await connection.fetch(query, *all_params)
            return row


@router.post("/stats/tagspercent")
async def get_stats_tagspercent(
    stat_filters: StatFilter,
    token_data: dict = Depends(verify_token)
):
    """
    Get tag percentage statistics for calls
    """
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if is_admin:
            # Admin users can see stats for all calls without phone restrictions
            query = f"""(SELECT
        arr.tags_json ->> 'tag' as label,
        count(arr.call_uuid)::numeric/ (SELECT COUNT(*) FROM {settings.DB_SCHEMA}.calls
            WHERE caller LIKE ($3)
            AND calle LIKE ($4)
            AND call_start_ts BETWEEN $1 and $2
        )*100 as value
    FROM
        {settings.DB_SCHEMA}.calls_tags t,
        jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid)
    WHERE
        t.call_uuid IN (
            SELECT call_uuid
            FROM {settings.DB_SCHEMA}.calls
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
    select 'ALL', 100"""
            row = await connection.fetch(
                query,
                stat_filters.startDate,
                stat_filters.endDate,
                stat_filters.caller,
                stat_filters.callee,
                stat_filters.spk
            )
            return row
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result
                return []
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""(SELECT
        arr.tags_json ->> 'tag' as label,
        count(arr.call_uuid)::numeric/ (SELECT COUNT(*) FROM {settings.DB_SCHEMA}.calls
            WHERE caller LIKE ($3)
            AND calle LIKE ($4)
            AND call_start_ts BETWEEN $1 and $2
        )*100 as value
    FROM
        {settings.DB_SCHEMA}.calls_tags t,
        jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid)
    WHERE
        t.call_uuid IN (
            SELECT call_uuid
            FROM {settings.DB_SCHEMA}.calls
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
    select 'ALL', 100"""
                row = await connection.fetch(
                    query,
                    stat_filters.startDate,
                    stat_filters.endDate,
                    stat_filters.caller,
                    stat_filters.callee,
                    stat_filters.spk
                )
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(6, 6+len(accessible_phones))])
                query = f"""(SELECT
        arr.tags_json ->> 'tag' as label,
        count(arr.call_uuid)::numeric/ (SELECT COUNT(*) FROM {settings.DB_SCHEMA}.calls
            WHERE (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
            AND caller LIKE ($3)
            AND calle LIKE ($4)
            AND call_start_ts BETWEEN $1 and $2
        )*100 as value
    FROM
        {settings.DB_SCHEMA}.calls_tags t,
        jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid)
    WHERE
        t.call_uuid IN (
            SELECT call_uuid
            FROM {settings.DB_SCHEMA}.calls
            WHERE (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
            AND caller LIKE ($3)
            AND calle LIKE ($4)
            AND call_start_ts BETWEEN $1 and $2
        )
        AND arr.tags_json ->> 'spk' = $5
    GROUP BY
        label
    ORDER BY
        label)
    union all
    select 'ALL', 100"""
                
                all_params = [stat_filters.startDate, stat_filters.endDate, stat_filters.caller, stat_filters.callee, stat_filters.spk] + accessible_phones
                row = await connection.fetch(query, *all_params)
            return row


@router.post("/stats/tagscount")
async def get_stats_tagscount(
    stat_filters: StatFilter,
    token_data: dict = Depends(verify_token)
):
    """
    Get tag count statistics for calls
    """
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if is_admin:
            # Admin users can see stats for all calls without phone restrictions
            query = f"""SELECT arr.tags_json ->> 'tag' as label,
            count(arr.call_uuid) as value
                FROM {settings.DB_SCHEMA}.calls_tags t,
            jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid)
                where t.call_uuid in (
                    SELECT call_uuid
                    FROM {settings.DB_SCHEMA}.calls
                    where caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                )
                and arr.tags_json ->> 'spk' = $5
                group by label
                order by label"""
            row = await connection.fetch(
                query,
                stat_filters.startDate,
                stat_filters.endDate,
                stat_filters.caller,
                stat_filters.callee,
                stat_filters.spk
            )
            return row
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result
                return []
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""SELECT arr.tags_json ->> 'tag' as label,
                count(arr.call_uuid) as value
                    FROM {settings.DB_SCHEMA}.calls_tags t,
                jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid)
                    where t.call_uuid in (
                        SELECT call_uuid
                        FROM {settings.DB_SCHEMA}.calls
                        where caller like ($3)
                        and calle like ($4)
                        and call_start_ts between $1 and $2
                    )
                    and arr.tags_json ->> 'spk' = $5
                    group by label
                    order by label"""
                row = await connection.fetch(
                    query,
                    stat_filters.startDate,
                    stat_filters.endDate,
                    stat_filters.caller,
                    stat_filters.callee,
                    stat_filters.spk
                )
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(6, 6+len(accessible_phones))])
                query = f"""SELECT  arr.tags_json ->> 'tag' as label,
                count(arr.call_uuid) as value
                    FROM {settings.DB_SCHEMA}.calls_tags t,
                jsonb_array_elements(tags_json) with ordinality arr(tags_json, call_uuid)
                    where t.call_uuid in (
                        SELECT call_uuid
                        FROM {settings.DB_SCHEMA}.calls
                        where (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
                        and caller like ($3)
                        and calle like ($4)
                        and call_start_ts between $1 and $2
                    )
                    and arr.tags_json ->> 'spk' = $5
                    group by label
                    order by label"""
                
                all_params = [stat_filters.startDate, stat_filters.endDate, stat_filters.caller, stat_filters.callee, stat_filters.spk] + accessible_phones
                row = await connection.fetch(query, *all_params)
            return row


@router.post("/stats/counts")
async def get_stats_counts(
    stat_filters: StatFilterCount, 
    token_data: dict = Depends(verify_token)
):
    """
    Get call count statistics
    """
    # Validate the input
    validator = StatFilterCountValidator(
        startDate=stat_filters.startDate,
        endDate=stat_filters.endDate,
        caller=stat_filters.caller,
        callee=stat_filters.callee,
        sampling=stat_filters.sampling
    )
    validator.validate_date_range()
    
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if is_admin:
            # Admin users can see stats for all calls without phone restrictions
            query = f"""
                SELECT date_trunc($5, call_start_ts) as "label",
                count(*) as "value"
                FROM {settings.DB_SCHEMA}.calls
                where caller like ($3)
                and calle like ($4)
                and call_start_ts between $1 and $2
                group by 1
                ORDER BY 1
            """
            row = await connection.fetch(
                query,
                stat_filters.startDate,
                stat_filters.endDate,
                stat_filters.caller,
                stat_filters.callee,
                stat_filters.sampling
            )
            return row
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result
                return []
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""
                    SELECT date_trunc($5, call_start_ts) as "label",
                    count(*) as "value"
                    FROM {settings.DB_SCHEMA}.calls
                    where caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                    group by 1
                    ORDER BY 1
                """
                row = await connection.fetch(
                    query,
                    stat_filters.startDate,
                    stat_filters.endDate,
                    stat_filters.caller,
                    stat_filters.callee,
                    stat_filters.sampling
                )
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(6, 6+len(accessible_phones))])
                query = f"""
                    SELECT date_trunc($5, call_start_ts) as "label",
                    count(*) as "value"
                    FROM {settings.DB_SCHEMA}.calls
                    where (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
                    and caller like ($3)
                    and calle like ($4)
                    and call_start_ts between $1 and $2
                    group by 1
                    ORDER BY 1
                """
                
                all_params = [
                    stat_filters.startDate, 
                    stat_filters.endDate, 
                    stat_filters.caller, 
                    stat_filters.callee, 
                    stat_filters.sampling
                ] + accessible_phones
                row = await connection.fetch(query, *all_params)
            return row


@router.post("/calls/")
async def get_calls(
    call_filter: CallFilter, 
    token_data: dict = Depends(verify_token)
):
    """
    Get calls based on filters
    """
    # Validate the input
    validator = CallFilterValidator(
        limit=call_filter.limit,
        offset=call_filter.offset,
        startDate=call_filter.startDate,
        endDate=call_filter.endDate,
        caller=call_filter.caller,
        callee=call_filter.callee,
        metadata_filters=call_filter.metadata_filters
    )
    validator.validate_date_range()
    # validator.validate_pagination_values()  # Comment out temporarily to avoid potential validation issues
    
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        # Get active metadata mappings
        mappings = await connection.fetch(
            f"""
            SELECT field_key, display_name, field_type
            FROM {settings.DB_SCHEMA}.metadata_mappings
            WHERE is_active = true
            ORDER BY sort_order
            """
        )
        
        # Build dynamic SELECT clause for metadata
        metadata_selects = []
        for mapping in mappings:
            field_key = mapping['field_key']
            display_name = mapping['display_name']
            # Convert dot notation to PostgreSQL JSON navigation
            json_path_parts = field_key.split('.')
            json_path_expr = f"cm.meta->>'{json_path_parts[0]}'"
            for part in json_path_parts[1:]:
                json_path_expr += f"->>'{part}'"
            metadata_selects.append(f"({json_path_expr}) AS \"{display_name}\"")
        
        metadata_join = f"LEFT JOIN {settings.DB_SCHEMA}.calls_meta cm ON c.call_uuid = cm.call_uuid"
        metadata_select_clause = ", " + ", ".join(metadata_selects) if metadata_selects else ""
        
        if is_admin:
            # Admin users can see all calls without phone restrictions
            query = f"""
            SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction
            {metadata_select_clause}
            FROM {settings.DB_SCHEMA}.calls c
            {metadata_join}
            WHERE c.call_start_ts BETWEEN $4 and $3
            and c.caller like ($5)
            and c.calle like ($6)
            {build_metadata_where_clause(call_filter.metadata_filters, 7)}
            order by c.call_end_ts desc limit $1 offset $2
            """
            # Prepare parameters for the query
            params = [
                call_filter.limit,
                call_filter.offset,
                call_filter.startDate,
                call_filter.endDate,
                call_filter.caller,
                call_filter.callee
            ]
            # Add metadata filter parameters if any
            if call_filter.metadata_filters:
                for key, value in call_filter.metadata_filters.items():
                    # Only add non-None values to prevent IndeterminateDatatypeError
                    if value is not None:
                        params.append(value)
            
            row = await connection.fetch(query, *params)
            return row
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result
                return []
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""
                SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction
                {metadata_select_clause}
                FROM {settings.DB_SCHEMA}.calls c
                {metadata_join}
                WHERE c.call_start_ts BETWEEN $4 and $3
                and c.caller like ($5)
                and c.calle like ($6)
                {build_metadata_where_clause(call_filter.metadata_filters, 7)}
                order by c.call_end_ts desc limit $1 offset $2
                """
                params = [
                    call_filter.limit,
                    call_filter.offset,
                    call_filter.startDate,
                    call_filter.endDate,
                    call_filter.caller,
                    call_filter.callee
                ]
                # Add metadata filter parameters if any
                if call_filter.metadata_filters:
                    for key, value in call_filter.metadata_filters.items():
                        # Only add non-None values to prevent IndeterminateDatatypeError
                        if value is not None:
                            params.append(value)
                
                row = await connection.fetch(query, *params)
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(7, 7+len(accessible_phones))])
                query = f"""
                SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction
                {metadata_select_clause}
                FROM {settings.DB_SCHEMA}.calls c
                {metadata_join}
                WHERE (c.caller = ANY(ARRAY[{phone_placeholders}]) OR c.calle = ANY(ARRAY[{phone_placeholders}]))
                AND c.call_start_ts BETWEEN $4 and $3
                and c.caller like ($5)
                and c.calle like ($6)
                {build_metadata_where_clause(call_filter.metadata_filters, 7 + len(accessible_phones))}
                order by c.call_end_ts desc limit $1 offset $2
                """
                
                params = [
                    call_filter.limit, 
                    call_filter.offset, 
                    call_filter.startDate, 
                    call_filter.endDate, 
                    call_filter.caller, 
                    call_filter.callee
                ] + accessible_phones
                # Add metadata filter parameters if any
                if call_filter.metadata_filters:
                    for key, value in call_filter.metadata_filters.items():
                        # Only add non-None values to prevent IndeterminateDatatypeError
                        if value is not None:
                            params.append(value)
                
                row = await connection.fetch(query, *params)
            return row

def build_metadata_where_clause(metadata_filters, start_param_index):
    """Build WHERE clause for metadata filters"""
    if not metadata_filters:
        return ""
    
    conditions = []
    param_index = start_param_index
    
    for key, value in metadata_filters.items():
        # Only include condition if value is not None to prevent IndeterminateDatatypeError
        if value is not None:
            # Use the field_key directly for filtering
            conditions.append(f"cm.meta->>'{key}' = ${param_index}")
            param_index += 1
    
    if conditions:
        return "AND " + " AND ".join(conditions)
    return ""



class CallFilterWordWithMetadata(CallFilterWord):
    metadata_filters: Optional[dict] = None


@router.post("/textsearch/")
async def get_calls_by_text_search(
    call_filter: CallFilterWordWithMetadata, 
    token_data: dict = Depends(verify_token)
):
    """
    Search calls by text content
    """
    # Validate the input
    validator = CallFilterWordValidator(
        limit=call_filter.limit,
        offset=call_filter.offset,
        startDate=call_filter.startDate,
        endDate=call_filter.endDate,
        caller=call_filter.caller,
        callee=call_filter.callee,
        words1=call_filter.words1,
        words2=call_filter.words2,
        metadata_filters=call_filter.metadata_filters
    )
    validator.validate_date_range()
    # validator.validate_pagination_values()
    
    # Format the word lists for the query
    formatted_words1 = ["'%"+x['value']+"%'" for x in call_filter.words1]
    formatted_words2 = ["'%"+x['value']+"%'" for x in call_filter.words2]
    formatted_transcription_filter = format_filter_transcription(formatted_words1, formatted_words2)
    
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        # Get active metadata mappings
        mappings = await connection.fetch(
            f"""
            SELECT field_key, display_name, field_type
            FROM {settings.DB_SCHEMA}.metadata_mappings
            WHERE is_active = true
            ORDER BY sort_order
            """
        )
        
        # Build dynamic SELECT clause for metadata
        metadata_selects = []
        for mapping in mappings:
            field_key = mapping['field_key']
            display_name = mapping['display_name']
            # Convert dot notation to PostgreSQL JSON navigation
            json_path_parts = field_key.split('.')
            json_path_expr = f"cm.meta->>'{json_path_parts[0]}'"
            for part in json_path_parts[1:]:
                json_path_expr += f"->>'{part}'"
            metadata_selects.append(f"({json_path_expr}) AS \"{display_name}\"")
        
        metadata_join = f"LEFT JOIN {settings.DB_SCHEMA}.calls_meta cm ON c.call_uuid = cm.call_uuid"
        metadata_select_clause = ", " + ", ".join(metadata_selects) if metadata_selects else ""
        
        if is_admin:
            # Admin users can see all calls without phone restrictions
            query = f"""
            SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction,
    arr.transcription ->> 'text' as text
    {metadata_select_clause}
        FROM {settings.DB_SCHEMA}.calls_transcription t,
    jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid)
    ,{settings.DB_SCHEMA}.calls c
    {metadata_join}
        where t.call_uuid in (
            SELECT call_uuid
            FROM {settings.DB_SCHEMA}.calls
            where caller like ($5)
            and calle like ($6)
            and call_start_ts between $3 and $4
            {build_metadata_where_clause(call_filter.metadata_filters, 7)}
        )
        and c.call_uuid = t.call_uuid
        {formatted_transcription_filter}
     order by c.call_end_ts desc limit $1 offset $2
     """
            # Prepare parameters for the query
            params = [
                call_filter.limit,
                call_filter.offset,
                call_filter.startDate,
                call_filter.endDate,
                call_filter.caller,
                call_filter.callee
            ]
            # Add metadata filter parameters if any
            if call_filter.metadata_filters:
                for key, value in call_filter.metadata_filters.items():
                    # Only add non-None values to prevent IndeterminateDatatypeError
                    if value is not None:
                        params.append(value)
            
            row = await connection.fetch(query, *params)
            return row
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result
                return []
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""
                SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction,
        arr.transcription ->> 'text' as text
        {metadata_select_clause}
            FROM {settings.DB_SCHEMA}.calls_transcription t,
        jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid)
        ,{settings.DB_SCHEMA}.calls c
        {metadata_join}
            where t.call_uuid in (
                SELECT call_uuid
                FROM {settings.DB_SCHEMA}.calls
                where caller like ($5)
                and calle like ($6)
                and call_start_ts between $3 and $4
                {build_metadata_where_clause(call_filter.metadata_filters, 7)}
            )
            and c.call_uuid = t.call_uuid
            {formatted_transcription_filter}
         order by c.call_end_ts desc limit $1 offset $2
         """
                params = [
                    call_filter.limit,
                    call_filter.offset,
                    call_filter.startDate,
                    call_filter.endDate,
                    call_filter.caller,
                    call_filter.callee
                ]
                # Add metadata filter parameters if any
                if call_filter.metadata_filters:
                    for key, value in call_filter.metadata_filters.items():
                        # Only add non-None values to prevent IndeterminateDatatypeError
                        if value is not None:
                            params.append(value)
                
                row = await connection.fetch(query, *params)
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(7, 7+len(accessible_phones))])
                query = f"""
                SELECT c.call_uuid, c.call_start_ts, c.caller, c.calle, c.duration, c.direction,
        arr.transcription ->> 'text' as text
        {metadata_select_clause}
            FROM {settings.DB_SCHEMA}.calls_transcription t,
        jsonb_array_elements(transcription) with ordinality arr(transcription, call_uuid)
        ,{settings.DB_SCHEMA}.calls c
        {metadata_join}
            where t.call_uuid in (
                SELECT call_uuid
                FROM {settings.DB_SCHEMA}.calls
                where (caller = ANY(ARRAY[{phone_placeholders}]) OR calle = ANY(ARRAY[{phone_placeholders}]))
                and caller like ($5)
                and calle like ($6)
                and call_start_ts between $3 and $4
                {build_metadata_where_clause(call_filter.metadata_filters, 7 + len(accessible_phones))}
            )
            and c.call_uuid = t.call_uuid
            {formatted_transcription_filter}
         order by c.call_end_ts desc limit $1 offset $2
         """
                
                params = [
                    call_filter.limit, 
                    call_filter.offset, 
                    call_filter.startDate, 
                    call_filter.endDate, 
                    call_filter.caller, 
                    call_filter.callee
                ] + accessible_phones
                # Add metadata filter parameters if any
                if call_filter.metadata_filters:
                    for key, value in call_filter.metadata_filters.items():
                        # Only add non-None values to prevent IndeterminateDatatypeError
                        if value is not None:
                            params.append(value)
                
                row = await connection.fetch(query, *params)
            return row


@router.post("/calls/stats")
async def get_calls_stats(
    call_stats_filters: CallStatsFilter, 
    token_data: dict = Depends(verify_token)
):
    """
    Get call statistics
    """
    # Validate the input
    validator = CallStatsFilterValidator(
        startDate=call_stats_filters.startDate,
        endDate=call_stats_filters.endDate,
        caller=call_stats_filters.caller,
        callee=call_stats_filters.callee,
        metadata_filters=call_stats_filters.metadata_filters
    )
    validator.validate_date_range()
    
    async with db.pool.acquire() as connection:
        # Check if user is admin
        is_admin = token_data.role == 'admin'
        
        if is_admin:
            # Admin users can see stats for all calls without phone restrictions
            query = f"""
                SELECT
                    direction,
                    COUNT(*) as count,
                    SUM(duration) as total_duration
                FROM {settings.DB_SCHEMA}.calls c
                LEFT JOIN {settings.DB_SCHEMA}.calls_meta cm ON c.call_uuid = cm.call_uuid
                WHERE call_start_ts BETWEEN $1 and $2
                AND caller LIKE $3
                AND calle LIKE $4
                {build_metadata_where_clause(call_stats_filters.metadata_filters, 5)}
                GROUP BY direction
                ORDER BY direction
            """
            # Prepare parameters for the query
            params = [
                call_stats_filters.startDate,
                call_stats_filters.endDate,
                call_stats_filters.caller,
                call_stats_filters.callee
            ]
            # Add metadata filter parameters if any
            if call_stats_filters.metadata_filters:
                for key, value in call_stats_filters.metadata_filters.items():
                    # Only add non-None values to prevent IndeterminateDatatypeError
                    if value is not None:
                        params.append(value)
            
            row = await connection.fetch(query, *params)
        else:
            # Regular users - get their accessible phone numbers
            accessible_phones = await get_user_accessible_phones(connection, token_data.username)
            if not accessible_phones:
                # If user has no accessible phones, return empty result with zeros
                stats = {
                    'incoming': {'count': 0, 'total_duration': 0},
                    'outgoing': {'count': 0, 'total_duration': 0},
                    'total': {'count': 0, 'total_duration': 0}
                }
                return stats
            
            # Construct the query with access control
            if '%' in accessible_phones:
                # User has full access
                query = f"""
                    SELECT
                        direction,
                        COUNT(*) as count,
                        SUM(duration) as total_duration
                    FROM {settings.DB_SCHEMA}.calls c
                    LEFT JOIN {settings.DB_SCHEMA}.calls_meta cm ON c.call_uuid = cm.call_uuid
                    WHERE call_start_ts BETWEEN $1 and $2
                    AND caller LIKE $3
                    AND calle LIKE $4
                    {build_metadata_where_clause(call_stats_filters.metadata_filters, 5)}
                    GROUP BY direction
                    ORDER BY direction
                """
                # Prepare parameters for the query
                params = [
                    call_stats_filters.startDate,
                    call_stats_filters.endDate,
                    call_stats_filters.caller,
                    call_stats_filters.callee
                ]
                # Add metadata filter parameters if any
                if call_stats_filters.metadata_filters:
                    for key, value in call_stats_filters.metadata_filters.items():
                        # Only add non-None values to prevent IndeterminateDatatypeError
                        if value is not None:
                            params.append(value)
                
                row = await connection.fetch(query, *params)
            else:
                # User has restricted access - filter by accessible phones
                phone_placeholders = ','.join([f'${i}' for i in range(5, 5+len(accessible_phones))])
                query = f"""
                    SELECT
                        direction,
                        COUNT(*) as count,
                        SUM(duration) as total_duration
                    FROM {settings.DB_SCHEMA}.calls c
                    LEFT JOIN {settings.DB_SCHEMA}.calls_meta cm ON c.call_uuid = cm.call_uuid
                    WHERE (c.caller = ANY(ARRAY[{phone_placeholders}]) OR c.calle = ANY(ARRAY[{phone_placeholders}]))
                    AND c.call_start_ts BETWEEN $1 and $2
                    AND c.caller LIKE $3
                    AND c.calle LIKE $4
                    {build_metadata_where_clause(call_stats_filters.metadata_filters, 5 + len(accessible_phones))}
                    GROUP BY direction
                    ORDER BY direction
                """
                all_params = [
                    call_stats_filters.startDate, 
                    call_stats_filters.endDate, 
                    call_stats_filters.caller, 
                    call_stats_filters.callee
                ] + accessible_phones
                # Add metadata filter parameters if any
                if call_stats_filters.metadata_filters:
                    for key, value in call_stats_filters.metadata_filters.items():
                        # Only add non-None values to prevent IndeterminateDatatypeError
                        if value is not None:
                            all_params.append(value)
                
                row = await connection.fetch(query, *all_params)
        
        # Convert the result to a dictionary format
        stats = {
            'incoming': {'count': 0, 'total_duration': 0},
            'outgoing': {'count': 0, 'total_duration': 0},
            'total': {'count': 0, 'total_duration': 0}
        }
        
        total_count = 0
        total_duration = 0
        
        for record in row:
            direction = record['direction']
            count = record['count']
            duration = record['total_duration']
            
            if direction == 'inbound':
                stats['incoming'] = {'count': count, 'total_duration': duration}
            elif direction == 'outbound':
                stats['outgoing'] = {'count': count, 'total_duration': duration}
                
            total_count += count
            total_duration += duration if duration else 0
            
        stats['total'] = {'count': total_count, 'total_duration': total_duration}
        
        return stats