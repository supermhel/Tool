"""Score proposers: advice only, with anti-hallucination checks."""

import asyncio
import json

import pytest

from app import proposers
from app.config import settings

CRIT = {"id": "sec", "label": "Security", "detail": "encryption, authentication and access control",
        "max": 10}
DOC = ("We use ISO 27001. All data uses AES-256 encryption at rest.\n"
       "Authentication relies on SSO with MFA. Lunch is free on Fridays.")


def run(coro):
    return asyncio.run(coro)


def test_rules_finds_best_evidence_and_never_scores():
    p = run(proposers.RulesProposer().propose(CRIT, DOC))
    assert "encryption" in p.evidence_quote or "Authentication" in p.evidence_quote
    assert p.proposed_score is None
    assert 0 < p.confidence <= 0.6 and p.provider == "rules"


def test_rules_no_match_gives_zero_confidence():
    p = run(proposers.RulesProposer().propose(CRIT, "Completely unrelated text about gardening."))
    assert p.confidence == 0 and p.evidence_quote == ""


class FakeClient:
    last_payload = None
    reply: dict | None = None
    error: Exception | None = None

    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None):
        FakeClient.last_payload = json
        if FakeClient.error:
            raise FakeClient.error

        class R:
            def raise_for_status(self): ...
            def json(self_inner):
                import json as j
                return {"message": {"content": j.dumps(FakeClient.reply)}}
        return R()


@pytest.fixture
def ollama(monkeypatch):
    monkeypatch.setattr(proposers.httpx, "AsyncClient", FakeClient)
    FakeClient.error = None
    FakeClient.reply = None
    return FakeClient


def test_ollama_verified_quote_is_kept(ollama):
    ollama.reply = {"proposed_score": 8, "confidence": 0.9,
                    "evidence_quote": "Authentication relies on SSO with MFA.",
                    "rationale": "Strong auth."}
    p = run(proposers.OllamaProposer().propose(CRIT, DOC))
    assert p.proposed_score == 8 and p.confidence == 0.9
    assert p.quote_verified is True and p.evidence_quote.startswith("Authentication")
    assert p.provider == settings.OLLAMA_MODEL


def test_ollama_request_is_schema_constrained_and_treats_bid_as_data(ollama):
    ollama.reply = {"proposed_score": 5, "confidence": 0.5, "evidence_quote": "", "rationale": ""}
    run(proposers.OllamaProposer().propose(CRIT, DOC))
    payload = ollama.last_payload
    assert payload["format"]["required"] and payload["options"]["temperature"] == 0
    assert "untrusted" in payload["messages"][0]["content"]
    assert "BID TEXT" in payload["messages"][1]["content"]


def test_ollama_fabricated_quote_is_dropped_and_confidence_capped(ollama):
    ollama.reply = {"proposed_score": 10, "confidence": 0.95,
                    "evidence_quote": "We hold SOC 2 Type II certification.",   # not in DOC
                    "rationale": "Certified."}
    p = run(proposers.OllamaProposer().propose(CRIT, DOC))
    assert p.evidence_quote == "" and p.quote_verified is False
    assert p.confidence <= 0.2 and "not found" in p.rationale


def test_ollama_quote_match_ignores_whitespace_and_case(ollama):
    ollama.reply = {"proposed_score": 7, "confidence": 0.7,
                    "evidence_quote": "all   DATA uses aes-256\n encryption at rest.", "rationale": ""}
    assert run(proposers.OllamaProposer().propose(CRIT, DOC)).quote_verified is True


@pytest.mark.parametrize("score", [11, -1, "8", True, None])
def test_ollama_invalid_score_discarded(ollama, score):
    ollama.reply = {"proposed_score": score, "confidence": 0.9, "evidence_quote": "", "rationale": ""}
    p = run(proposers.OllamaProposer().propose(CRIT, DOC))
    assert p.proposed_score is None and p.confidence <= 0.2


def test_ollama_failure_degrades_to_rules(ollama):
    ollama.error = ConnectionError("refused")
    p = run(proposers.OllamaProposer().propose(CRIT, DOC))
    assert p.provider == "rules-fallback" and p.proposed_score is None


def test_ollama_garbage_reply_degrades_to_rules(ollama):
    class Bad(FakeClient):
        async def post(self, url, json=None):
            class R:
                def raise_for_status(self): ...
                def json(self_inner): return {"message": {"content": "not json"}}
            return R()
    proposers.httpx.AsyncClient = Bad  # restored by the monkeypatch fixture
    assert run(proposers.OllamaProposer().propose(CRIT, DOC)).provider == "rules-fallback"


def test_provider_selection(monkeypatch):
    assert isinstance(proposers.get_proposer(), proposers.RulesProposer)
    monkeypatch.setattr(settings, "PROPOSER", "ollama")
    assert isinstance(proposers.get_proposer(), proposers.OllamaProposer)
    monkeypatch.setattr(settings, "PROPOSER", "whatever")
    assert isinstance(proposers.get_proposer(), proposers.RulesProposer)


def test_propose_all_covers_every_criterion():
    crits = [CRIT, {"id": "price", "label": "Price", "max": 10}]
    out = run(proposers.propose_all(crits, DOC))
    assert [p.criterion_id for p in out] == ["sec", "price"]
    json.dumps([p.model_dump() for p in out])
