"""Pydantic schemas for every LLM output. The Router validates against these;
nothing half-parsed ever reaches the database."""

from typing import Literal

from pydantic import BaseModel, Field


class Classification(BaseModel):
    category: Literal["lead", "document", "status_update", "other"]
    confidence: float = Field(ge=0.0, le=1.0)


class LeadRecord(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    reference: str | None = None
    intent: str | None = None


class KeyDates(BaseModel):
    acceptance: str | None = None
    earnest_money: str | None = None
    due_diligence: str | None = None
    closing: str | None = None


class DocumentRecord(BaseModel):
    parties: list[str] = []
    amounts: list[float] = []
    key_dates: KeyDates = KeyDates()
    reference: str | None = None
