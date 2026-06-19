"""Pydantic schemas — API input/output contracts."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    template_id: str = Field(..., examples=["process"])
    subject: str = Field(..., description="Entity being evaluated (process name, system, customer…)",
                         examples=["Onboarding process"])
    scores: dict[str, float] = Field(..., description="Scores per criterion {criterion_id: value}",
                                     examples=[{"steps": 8, "bottlenecks": 6}])
    notes: Optional[str] = Field(None, description="Free-form evaluator comment")


class CriterionDetail(BaseModel):
    id: str
    label: str
    detail: str
    value: float
    max: float
    weight: float
    contribution: float


class Ticket(BaseModel):
    id: str
    template_id: str
    template_name: str
    subject: str
    score: float
    grade: str
    grade_label: str
    details: list[CriterionDetail]
    notes: Optional[str] = None
    created_at: datetime


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user"])
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    ticket_id: Optional[str] = Field(None, description="Restrict context to a specific ticket")


class ChatResponse(BaseModel):
    reply: str
    model: str
    grounded_on: list[str] = Field(default_factory=list,
                                   description="IDs of tickets used as context")
