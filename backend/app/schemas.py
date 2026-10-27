from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Status = Literal["new", "contacted", "in_progress", "completed", "cancelled"]


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    category: str
    short_description: str
    description: str
    stages: str
    unit: str
    base_price_rub: Decimal
    is_active: bool
    sort_order: int


class ServiceWrite(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=180)
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=120)
    short_description: str = Field(min_length=5, max_length=500)
    description: str = Field(min_length=5, max_length=4000)
    stages: str = Field(min_length=3, max_length=1500)
    unit: str = Field(default="м²", min_length=1, max_length=24)
    base_price_rub: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)


class ServicePatch(BaseModel):
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$", max_length=180)
    name: str | None = Field(default=None, min_length=2, max_length=180)
    category: str | None = Field(default=None, min_length=2, max_length=120)
    short_description: str | None = Field(default=None, min_length=5, max_length=500)
    description: str | None = Field(default=None, min_length=5, max_length=4000)
    stages: str | None = Field(default=None, min_length=3, max_length=1500)
    unit: str | None = Field(default=None, min_length=1, max_length=24)
    base_price_rub: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class ItemIn(BaseModel):
    service_id: int
    quantity: Decimal = Field(
        ge=Decimal("0.1"), le=Decimal("10000"), max_digits=12, decimal_places=2
    )


class QuoteIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1, max_length=20)

    @field_validator("items")
    @classmethod
    def unique_items(cls, value):
        if len({item.service_id for item in value}) != len(value):
            raise ValueError("Позиции услуг не должны повторяться")
        return value


class QuoteLine(BaseModel):
    service_id: int
    name: str
    unit: str
    quantity: Decimal
    unit_price_rub: Decimal
    line_total_rub: Decimal


class QuoteOut(BaseModel):
    items: list[QuoteLine]
    estimated_total_rub: Decimal
    currency: str = "RUB"
    warning: str = "Стоимость предварительная и уточняется после осмотра и согласования условий работ."


class OrderCreate(QuoteIn):
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=30)
    email: EmailStr | None = Field(default=None, max_length=254)
    object_location: str | None = Field(default=None, max_length=250)
    desired_date: date | None = None
    comment: str | None = Field(default=None, max_length=2000)
    consent_accepted: Literal[True]

    @field_validator("customer_name", "object_location", "comment", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class OrderCreated(BaseModel):
    public_number: str
    status: Status
    estimated_total_rub: Decimal
    currency: str = "RUB"
    created_at: datetime


class TrackIn(BaseModel):
    public_number: str = Field(pattern=r"^SC-[A-Z0-9]{10}$")
    phone: str = Field(min_length=10, max_length=30)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    service_id: int | None
    service_name_snapshot: str
    unit_snapshot: str
    quantity: Decimal
    unit_price_snapshot: Decimal
    line_total_rub: Decimal


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    old_status: str | None
    new_status: str
    created_at: datetime


class TrackOut(BaseModel):
    public_number: str
    status: Status
    estimated_total_rub: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]


class AdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class OrderPatch(BaseModel):
    status: Status | None = None
    admin_note: str | None = Field(default=None, max_length=2000)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1500)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)
