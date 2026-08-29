from pydantic import BaseModel, EmailStr, UUID4, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum

# --- ENUMS ---
class UserRole(str, Enum):
    admin = "admin"
    pentester = "pentester"
    read_only = "read_only"

class TestStatus(str, Enum):
    not_planned = "Not Planned"
    planned = "Planned"
    scheduled = "Scheduled"
    completed = "Completed"
    unable = "Unable"

# --- SERVICENOW SYNC ---
class SnowSyncRequest(BaseModel):
    pass

# --- LOCATIONS & COUNTRIES ---
class LocationBase(BaseModel):
    name: str
    is_active: bool = True

class LocationResponse(LocationBase):
    id: UUID4

class CountryBase(BaseModel):
    code: str
    name: str
    region_id: Optional[UUID4] = None
    is_active: bool = True
    kiss24_uuid: Optional[str] = None

class CountryResponse(CountryBase):
    id: UUID4

# --- SERVICE LANES ---
class ServiceLaneBase(BaseModel):
    name: str
    max_concurrent_per_week: Optional[int] = None
    theme_color: str = "#3b82f6"
    default_credits: float = 2.0
    default_duration_weeks: int = 1
    target_goal: Optional[int] = 0
    is_active: bool = True
    display_order: int = 99
    auto_provision_workspace: bool = False
    requires_mitre: bool = False

class ServiceLaneResponse(ServiceLaneBase):
    id: UUID4

class PlaceholderCreate(BaseModel):
    service_lane_id: UUID4
    year: int
    week: int

class PlaceholderResponse(PlaceholderCreate):
    id: UUID4
    credits: int

    class Config:
        from_attributes = True

class ServiceLaneTemplatesUpdate(BaseModel):
    intro_email_template: Optional[str] = None
    final_email_template: Optional[str] = None

# --- USERS ---
class UserBase(BaseModel):
    name: str
    role: UserRole
    base_capacity: float = 1.0
    start_week: int = 1
    start_year: int = 2024
    end_week: Optional[int] = None
    end_year: Optional[int] = None
    location_id: Optional[UUID4] = None
    kiss24_uuid: Optional[str] = None
    kiss24_api_key: Optional[str] = None

class UserCreate(UserBase):
    email: EmailStr  # We invite by email now

class UserResponse(UserBase):
    id: UUID4
    email: EmailStr

class Kiss24KeyUpdate(BaseModel):
    api_key: str

class NotificationResponse(BaseModel):
    id: UUID4
    message: str
    type: str
    created_at: datetime

class ApiKeyCreate(BaseModel):
    name: str

# --- ASSETS ---
class AssetBase(BaseModel):
    name: str
    asset_type_id: UUID4
    country_id: Optional[UUID4] = None
    service_forecast_id: Optional[UUID4] = None
    category_id: Optional[UUID4] = None

class RawAssetCreate(AssetBase):
    description: Optional[str] = None
    business_critical: Optional[int] = None
    confidentiality_rating: Optional[int] = None
    integrity_rating: Optional[int] = None
    availability_rating: Optional[int] = None
    facing_internet: bool = False
    duplicate_allowed: bool = False
    snow_number: Optional[str] = None
    team_note: Optional[str] = None
    kiss24_asset_id: Optional[str] = None
    is_kpi: bool = False
    is_critical: bool = False

class AssetResponse(AssetBase):
    id: UUID4
    raw_asset_id: UUID4
    is_assigned: bool = False
    is_archived: bool = False
    archived_years: List[int] = []

class PromoteAssetRequest(BaseModel):
    raw_asset_ids: List[UUID4]

class BulkAssetRequest(BaseModel):
    raw_asset_ids: List[UUID4]

class AssetTypeBase(BaseModel):
    name: str

class BulkServiceUpdateRequest(BaseModel):
    asset_ids: List[UUID4]
    service_lane_id: UUID4

# --- TESTS & ASSIGNMENTS ---
class TestBase(BaseModel):
    name: str
    service_lane_id: UUID4
    category_id: Optional[UUID4] = None
    credits_per_week: float
    duration_weeks: float
    start_week: Optional[int] = None
    start_year: Optional[int] = None
    status: TestStatus = TestStatus.not_planned
    is_tentative: bool = False
    drive_folder_id: Optional[str] = None
    drive_folder_url: Optional[str] = None
    kiss24: Optional[UUID4] = None

class TestCreate(TestBase):
    asset_ids: List[UUID4] = []

class TestResponse(TestBase):
    id: UUID4
    asset_ids: List[UUID4] = []

class TestSchedule(BaseModel):
    start_week: int
    start_year: int

class SecureNotePayload(BaseModel):
    note: str

class BulkTestCreate(BaseModel):
    asset_ids: List[UUID4]

class AssignmentCreate(BaseModel):
    test_id: UUID4
    user_id: UUID4
    week_number: int
    year: int
    allocated_credits: float

class AssignmentBase(BaseModel):
    test_id: UUID4
    user_id: UUID4
    week_number: int
    year: int
    allocated_credits: float

class AssignmentResponse(AssignmentBase):
    id: UUID4

class TestAnalysisResponse(BaseModel):
    status: str
    analysis_text: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class RequirementCreate(BaseModel):
    description: str

class MilestoneUpdate(BaseModel):
    step_name: str
    is_completed: bool

# Events
class EventType(str, Enum):
    national_holiday = "national_holiday"
    team_day = "team_day"
    personal_time_off = "personal_time_off"
    sick_day = "sick_day"
    working_from_abroad = "working_from_abroad"

class EventBase(BaseModel):
    event_type: EventType
    start_date: date
    end_date: date
    location_id: Optional[UUID4] = None

class EventCreate(EventBase):
    user_id: Optional[UUID4] = None

class EventResponse(EventBase):
    id: UUID4
    user_id: Optional[UUID4] = None

class ServiceCategoryBase(BaseModel):
    name: str
    target_goal: int
    service_lane_id: Optional[UUID4] = None

class ServiceCategoryCreate(ServiceCategoryBase):
    pass

class ServiceCategoryResponse(ServiceCategoryBase):
    id: UUID4

# --- Contact mapping ---
class ContactMappingItem(BaseModel):
    id: str # country_id or raw_asset_id
    is_stakeholder: bool
    is_developer: bool

class ContactSyncPayload(BaseModel):
    contact_id: Optional[str] = None
    email: EmailStr
    full_name: Optional[str] = None
    countries: List[ContactMappingItem] = []
    assets: List[ContactMappingItem] = []

# --- Luigi ---
class SendEmailPayload(BaseModel):
    to: str
    cc: str
    subject: str
    body: str

class MeetingProposalRequest(BaseModel):
    meeting_type: str
    emails: List[str]

# --- kiss24 ----
class Kiss24ContextBase(BaseModel):
    id: UUID4
    name: str

    class Config:
        from_attributes = True

class Kiss24VulnTypeBase(BaseModel):
    id: UUID4
    name: str
    contexts: List[Kiss24ContextBase] = [] # The Many-to-Many nested list!

    class Config:
        from_attributes = True

#  Sync Endpoint Response Schema
class SyncVulnTypesResponse(BaseModel):
    status: str
    message: str
    contexts_synced: int
    vuln_types_synced: int
    associations_created: int

class LuigiVulnCallback(BaseModel):
    user_email: str
    html: str
    suggested_type: str

# public key
class PublicKeyUpdate(BaseModel):
    public_key: str

class ReconcileAssetPayload(BaseModel):
    mario_raw_asset_id: str
    kiss24_uuid: str
    snow_number: str

class BulkReconcileAssetPayload(BaseModel):
    assets: List[ReconcileAssetPayload]

class RagChatRequest(BaseModel):
    query: str
    session_id: UUID4
    test_id: Optional[UUID4] = None
    asset_id: Optional[UUID4] = None

class RagAIResponse(BaseModel):
    answer: str = Field(description="The response text to the user's question.")
    used_sources: List[str] = Field(description="List of exact document file names actually used to answer the question. Empty if no sources were used or no answer was found.")