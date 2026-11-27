from datetime import date, datetime

from pydantic import (BaseModel, ConfigDict, Field, field_validator,
                      model_validator)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ResourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    price_per_hour: float = Field(ge=0)
    category_id: int | None = None
    image_url: str | None = Field(default=None, max_length=255)


class ResourceOut(ResourceIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    in_maintenance: bool = False


class RegisterRequest(BaseModel):
    email: str = Field(max_length=100)
    password: str = Field(min_length=6, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    team_id: int | None = None
    new_team_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def email_usv(cls, value: str) -> str:
        value = value.strip().lower()
        local_part, _, domain = value.partition("@")
        if not local_part or not (domain == "usv.ro"
                                  or domain.endswith(".usv.ro")):
            raise ValueError("Foloseste emailul institutional (@usv.ro sau "
                             "@student.usv.ro)")
        return value

    @field_validator("new_team_name")
    @classmethod
    def clean_team_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        return value or None

    @model_validator(mode="after")
    def one_team_choice(self):
        if self.team_id is not None and self.new_team_name is not None:
            raise ValueError("Alege o echipa existenta sau creeaza una noua, "
                             "nu amandoua")
        return self


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    affiliation_date: date
    team_id: int | None


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    reservation_id: int | None = None
    message: str
    is_read: bool
    created_at: datetime


class SlotOut(BaseModel):
    start_time: datetime
    end_time: datetime
    status: str


class ReservationIn(BaseModel):
    resource_id: int
    team_id: int | None = None
    start_time: datetime
    end_time: datetime
    purpose: str | None = Field(default=None, max_length=255)

    @field_validator("start_time", "end_time")
    @classmethod
    def to_local_naive(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def check_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("Ora de sfarsit trebuie sa fie dupa ora de start")
        return self


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    resource_name: str | None = None
    team_id: int
    team_name: str | None = None
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    start_time: datetime
    end_time: datetime
    price: float | None
    discount: float
    final_price: float | None
    status: str
    purpose: str | None = None
    created_at: datetime | None = None


class MaintenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    start_time: datetime
    end_time: datetime
    reason: str | None
    admin_id: int | None


class MaintenanceIn(BaseModel):
    start_time: datetime
    end_time: datetime
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("start_time", "end_time")
    @classmethod
    def to_local_naive(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def check_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("Ora de sfarsit trebuie sa fie dupa ora de start")
        return self


class MaintenanceCreated(BaseModel):
    maintenance: MaintenanceOut
    cancelled_reservations: int


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class QuoteOut(BaseModel):
    price: float
    discount: float
    final_price: float


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class ResourceStats(BaseModel):
    resource_id: int
    resource_name: str
    reserved_hours: float
    occupancy_percent: float


class WeekStats(BaseModel):
    week_start: date
    active_reservations: int
    in_maintenance: int
    resources: list[ResourceStats]


class ImageUpload(BaseModel):
    filename: str = Field(max_length=200)
    content_base64: str
