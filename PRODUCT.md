# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: **tender and RFP evaluation committees**: procurement officers, evaluators and committee chairs who must score competing bids against pre-published weighted criteria and defend the result if a losing bidder challenges it. Confirmed by the owner as the intended direction; the demand itself is **not yet validated** (no customer conversations have happened).

Secondary: anyone scoring a process, a system or a customer against weighted criteria (the original generic scorecard, kept as the engine and as demo content).

## Product Purpose

Make a bid evaluation defensible. Evaluators score independently and blind, every score carries a written justification, disputed criteria are reconciled explicitly, and the award is sealed in tamper-evident records. A weight-sensitivity analysis shows whether a different weighting would have changed the winner. Success: a committee can produce an award report and per-bidder debriefs it would stand behind in a challenge.

## Positioning

A tender-evaluation workbench that is small, self-hostable and honest about AI: the model only suggests evidence and a human enters every score. Neighbouring e-procurement suites bundle evaluation inside heavy platforms; generic form and spreadsheet tools have no blind scoring, divergence handling or audit trail.

## Operating Context

- Scoring happens at a desk, often over days, by several people who must not see each other's scores until scoring is closed.
- Output leaves the tool as printed or PDF documents (award report, debrief letters) and as JSON through the API.
- Bids are commercially confidential, which is why a local model option matters.
- Criteria and weights are fixed before any bid is scored.

## Capabilities and Constraints

- Weighted-criteria scoring to a 0-100 score and A-E grade; built-in templates (process, system, sentiment) and custom versioned templates imported from JSON, YAML or CSV.
- Tender workflow: blind scoring, divergence flags, consensus, award with sealed tickets, award report and debrief letters.
- Organisation-scoped API keys; with keys enabled a key's label is the evaluator identity.
- Hash-chained tickets and audit log (tamper-evident, not tamper-proof).
- A REST API is the contract; the web UI is one client of it. Chatbot over tickets with a rule-based fallback.
- Undecided: pricing and licensing, a production deployment, per-jurisdiction procurement-law compliance (the tool makes no legal claims), and any provider for score proposals beyond the offline rules baseline and a local Ollama model.

## Brand Commitments

Confirmed as binding by the owner:

- **Humans decide every score.** AI suggests evidence; it never writes a score.
- **Local-first AI option.** Bid and ticket data can stay on the customer's own infrastructure.
- **Every score has a written reason.** Justification is mandatory.
- **English UI.** Interface copy is English; no French strings.

## Evidence on Hand

- A working application and its test suite (212 backend tests, about 98% line coverage).
- Synthetic demonstration data only (the example bidders Acme, Globex and Initech in the sensitivity calculator). There are **no real customers, tenders, benchmarks or testimonials**; none may be invented.
- `cadrage-projet-tool.html` is an early planning draft, not a specification or source of truth.

## Product Principles

1. Defensibility over convenience: anything that weakens the audit trail needs an explicit reason.
2. The human decides; software shows evidence, flags divergence and does the arithmetic.
3. Show the arithmetic: scores, weights, spreads and tipping points are always inspectable.
4. Be honest about limits: state what the integrity guarantees do and do not cover.
5. Small and self-hostable beats a platform.

## Accessibility & Inclusion

Target WCAG AA: text at least 4.5:1, visible keyboard focus, form controls labelled, reduced-motion respected. Evaluators work long sessions, so density must stay readable.
