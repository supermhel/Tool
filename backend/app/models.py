"""Pydantic schemas — API input/output contracts."""

from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, StrictFloat, StrictInt, field_validator, model_validator

Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")]
Number = Union[StrictInt, StrictFloat]
Text120 = Annotated[str, Field(min_length=1, max_length=120)]


# ── templates ────────────────────────────────────────────────────────────────

class CriterionIn(BaseModel):
    id: Slug
    label: Annotated[str, Field(min_length=1, max_length=80)]
    detail: Annotated[str, Field(max_length=300)] = ""
    weight: Annotated[float, Field(gt=0, le=100)]
    max: Annotated[float, Field(gt=0, le=1000)]


class ScopeExcluded(BaseModel):
    label: Annotated[str, Field(max_length=120)]
    ref: Annotated[str, Field(max_length=60)] = ""


class Scope(BaseModel):
    covered: list[Annotated[str, Field(max_length=120)]] = Field(default_factory=list, max_length=20)
    excluded: list[ScopeExcluded] = Field(default_factory=list, max_length=20)


class TemplateIn(BaseModel):
    id: Slug
    name: Annotated[str, Field(min_length=1, max_length=80)]
    description: Annotated[str, Field(max_length=300)] = ""
    color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")] = "#5b8cff"
    criteria: Annotated[list[CriterionIn], Field(min_length=1, max_length=30)]
    scope: Scope = Field(default_factory=Scope)

    @field_validator("criteria")
    @classmethod
    def _unique_ids(cls, v):
        ids = [c.id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion ids must be unique")
        return v


class TemplateImport(BaseModel):
    """Raw file content sent by the client; parsed server-side."""
    filename: Annotated[str, Field(max_length=200)]
    content: Annotated[str, Field(max_length=100_000)]


# ── evaluations / tickets ────────────────────────────────────────────────────

class EvaluationRequest(BaseModel):
    template_id: Annotated[str, Field(min_length=1, max_length=60)] = Field(..., examples=["process"])
    template_version: Optional[int] = Field(None, ge=1, description="Defaults to the latest version")
    subject: Annotated[str, Field(min_length=1, max_length=200)] = Field(
        ..., description="Entity being evaluated (process name, system, customer…)",
        examples=["Onboarding process"])
    scores: Annotated[dict[str, Number], Field(max_length=50)] = Field(
        ..., description="Score per criterion {criterion_id: value}; every criterion is required",
        examples=[{"steps": 8, "bottlenecks": 6}])
    notes: Optional[Annotated[str, Field(max_length=2000)]] = Field(None, description="Free-form evaluator comment")

    @field_validator("subject")
    @classmethod
    def _strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("subject must not be blank")
        return v


class CriterionDetail(BaseModel):
    id: str
    label: str
    detail: str = ""
    value: float
    max: float
    weight: float
    contribution: float


class Ticket(BaseModel):
    id: str
    template_id: str
    template_name: str
    template_version: int = 1
    subject: str
    score: float
    grade: str
    grade_label: str
    details: list[CriterionDetail]
    notes: Optional[str] = None
    tender_id: Optional[str] = None
    created_at: datetime
    prev_hash: str = ""
    hash: str = ""


# ── chat ─────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=2000)]


class ChatRequest(BaseModel):
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=20)]
    ticket_id: Optional[str] = Field(None, description="Restrict context to a specific ticket")


class ChatResponse(BaseModel):
    reply: str
    model: str
    grounded_on: list[str] = Field(default_factory=list,
                                   description="IDs of tickets used as context")


# ── tenders ──────────────────────────────────────────────────────────────────

class TenderIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=160)]
    template_id: Annotated[str, Field(min_length=1, max_length=60)]
    template_version: Optional[int] = Field(None, ge=1)
    bidders: Annotated[list[Text120], Field(min_length=2, max_length=50)]
    evaluators: Annotated[list[Annotated[str, Field(min_length=1, max_length=80)]],
                          Field(min_length=1, max_length=20)]
    divergence_threshold: Annotated[float, Field(ge=0.05, le=1.0)] = Field(
        0.3, description="A criterion is flagged when evaluators' scores differ by more "
                         "than this share of the scale")

    @model_validator(mode="after")
    def _distinct(self):
        for label, names in (("bidders", self.bidders), ("evaluators", self.evaluators)):
            folded = [n.strip().lower() for n in names]
            if len(folded) != len(set(folded)):
                raise ValueError(f"{label} must be distinct")
        return self


class TenderScoreIn(BaseModel):
    bidder_id: str
    evaluator: str
    criterion_id: str
    value: Number
    justification: Annotated[str, Field(min_length=10, max_length=2000)]


class TenderConsensusIn(BaseModel):
    bidder_id: str
    criterion_id: str
    value: Number
    justification: Annotated[str, Field(min_length=10, max_length=2000)]


class ProposeIn(BaseModel):
    bidder_id: str
    document_text: Annotated[str, Field(min_length=1, max_length=50_000)]


# ── sensitivity (stateless) ──────────────────────────────────────────────────

class SensCriterion(BaseModel):
    id: Slug
    label: Annotated[str, Field(max_length=80)] = ""
    weight: Annotated[float, Field(gt=0, le=1000)]
    max: Annotated[float, Field(gt=0, le=1000)] = 10


class SensBidder(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    scores: Annotated[dict[str, Number], Field(max_length=30)]


class SensitivityRequest(BaseModel):
    criteria: Annotated[list[SensCriterion], Field(min_length=1, max_length=30)]
    bidders: Annotated[list[SensBidder], Field(min_length=2, max_length=50)]
    delta: Annotated[float, Field(gt=0, le=1)] = Field(
        0.2, description="Relative weight change considered 'small' (0.2 = ±20%)")

    @model_validator(mode="after")
    def _consistent(self):
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion ids must be unique")
        names = [b.name.strip().lower() for b in self.bidders]
        if len(names) != len(set(names)):
            raise ValueError("bidder names must be distinct")
        return self
