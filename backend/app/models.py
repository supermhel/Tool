"""Schémas Pydantic — contrat d'entrée/sortie de l'API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    template_id: str = Field(..., examples=["process"])
    subject: str = Field(..., description="Objet évalué (nom du processus, système, client...)",
                         examples=["Processus d'onboarding"])
    scores: dict[str, float] = Field(..., description="Notes par critère {criterion_id: note}",
                                     examples=[{"steps": 8, "bottlenecks": 6}])
    notes: Optional[str] = Field(None, description="Commentaire libre de l'évaluateur")


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
    ticket_id: Optional[str] = Field(None, description="Contextualise la réponse sur un ticket précis")


class ChatResponse(BaseModel):
    reply: str
    model: str
    grounded_on: list[str] = Field(default_factory=list,
                                   description="IDs des tickets utilisés comme contexte")
