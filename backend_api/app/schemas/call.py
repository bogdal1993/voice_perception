from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CallFilter(BaseModel):
    limit: int
    offset: int
    startDate: datetime
    endDate: datetime
    caller: str = "%"
    callee: str = "%"
    metadata_filters: Optional[dict] = None


class CallFilterWord(BaseModel):
    limit: int
    offset: int
    startDate: datetime
    endDate: datetime
    caller: str = "%"
    callee: str = "%"
    words1: List[dict] = [{"value": "%"}]
    words2: List[dict] = [{"value": "%"}]
    metadata_filters: Optional[dict] = None


class StatFilter(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str
    callee: str
    spk: str


class StatFilterWords(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str
    callee: str
    spk: str
    limit: int
    part: List[str] = []


class StatFilterCount(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str
    callee: str
    sampling: str = "day"


class CallStatsFilter(BaseModel):
    startDate: datetime
    endDate: datetime
    caller: str = "%"
    callee: str = "%"
    metadata_filters: Optional[dict] = None


class TagItem(BaseModel):
    tag_id: int
    tag_name: str
    tag_spk: str
    tag_texts: List[str]


class MentorCreate(BaseModel):
    username: str


class MentorPhoneAccess(BaseModel):
    phone_number: str


class MetadataMappingCreate(BaseModel):
    field_key: str
    display_name: str
    field_type: str
    is_active: bool = True
    sort_order: int = 0
    description: Optional[str] = None


class MetadataMappingUpdate(BaseModel):
    field_key: Optional[str] = None
    display_name: Optional[str] = None
    field_type: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None


class MetadataMappingItem(BaseModel):
    mapping_id: int
    field_key: str
    display_name: str
    field_type: str
    is_active: bool
    sort_order: int
    created_at: datetime
    created_by: Optional[int] = None
    description: Optional[str] = None


class MetadataMappingFilter(BaseModel):
    limit: int = 100
    offset: int = 0
    field_type: Optional[str] = None
    is_active: Optional[bool] = None
    search: Optional[str] = None