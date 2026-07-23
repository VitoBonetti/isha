from pydantic import BaseModel, EmailStr, UUID4
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

class ServiceLaneResponse(ServiceLaneBase):
    id: UUID4

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

class UserCreate(UserBase):
    email: EmailStr  # We invite by email now

class UserResponse(UserBase):
    id: UUID4
    email: EmailStr

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

class AssetResponse(AssetBase):
    id: UUID4
    raw_asset_id: UUID4
    is_assigned: bool = False

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
    drive_folder_id: Optional[str] = None
    drive_folder_url: Optional[str] = None

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