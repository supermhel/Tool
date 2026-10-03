# Status — Tool (2026-10-01, after verification and review pass)

## Just done
Verified the earlier work, closed most open items, and ran two independent subagent reviews (backend: opus with `engineering:code-review`; frontend: `cavecrew-reviewer`). Treated every finding as a claim: wrote failing regression tests first (`backend/tests/test_review_fixes.py`), then fixed. Nothing is committed.

- **Backend review: 7 real defects, all reproduced and fixed:** lost updates and double awards from unsynchronised tender writes (now optimistic compare-and-set, exclusive resumable award); phantom chain entry after a failed head update; SQLite CAS not atomic across connections (`BEGIN IMMEDIATE`); ranking on rounded totals (now exact); huge-int 500s; import 500s; unbounded tender size (cap 3,000 scores). Plus a sensitivity tie edge case.
- **Frontend review:** 3 of 6 claims real (consensus field cleared → saved 0; misleading blind-scoring text; undebounced slider), fixed. 3 rejected after checking (stale-closure "critical", blob revoke, contrast "fix" in the wrong direction).
- **Closed open items:** per-evaluator identity (key label = evaluator, `GET /me`), Upstash pooled client + real-HTTP fake servers, chain CAS, `PRODUCT.md` and `DESIGN.md` written from your answers (tender committees, "The Instrument Panel", four binding commitments).

## Reality Map
| Item | State | Evidence |
|------|-------|----------|
| Backend suite | DONE | PROVEN: 204 passed, 97.8% coverage (Python 3.13 local). An earlier 189-test run also passed on Python 3.12 in Docker. |
| Docker images build + Python 3.12 | DONE | PROVEN: both Dockerfiles built; final 204 tests pass on Python 3.12 in a container (97.8%); verify images removed |
| Review fixes (races, CAS, ranking, 500s) | DONE | PROVEN: 15 regression tests failed on the reviewed code, pass now; CAS mutation-checked |
| Evaluator identity under keys | DONE | PROVEN: `test_auth.py` + live UI (organiser key blocked, alice key locked to alice) |
| Report/debrief blob tabs | DONE | PROVEN with authenticated fetch of the blob content; the real new-tab navigation itself was mocked, not observed |
| CI replication (2026-10-03) | DONE | PROVEN: fresh venv from `requirements-dev.txt` → 204 passed, 97.8%; `npm ci` + build + `npm audit --omit=dev --audit-level=high` → 0 |
| Frontend | DONE | PROVEN: build 204 kB, detector 0 findings, 375 px no overflow, flows driven in the UI |
| Dev-only npm advisory (`braces` via tailwindcss 3) | OPEN, accepted | Appeared 2026-10-03: stack-exhaustion DoS, **no patched release exists** (affects all versions); the only npm "fix" is a breaking Tailwind 3→4 migration. Build-time glob library fed our own config, not shipped; production audit is 0. Revisit when braces or Tailwind 4 migration lands |
| Secrets / hygiene | DONE | PROVEN: no key-like strings in git-visible files, no tracked `.env`/`.db`, stray `.coverage` removed and ignored |
| Vercel | PARTIAL | Branch preview deployment of the new code is READY (build OK; SSO-protected, so the running app was not exercised). Production still runs old commit `fb7750b`; it updates when PR #1 is merged to `main` |
| Ollama / Upstash real services | OPEN | Verified over real HTTP against local fakes only; neither real service was available |
| CI workflow | DONE | PROVEN: first GitHub run on PR #1 (draft) → 4/4 checks passing, 0 failing, merge state CLEAN (2026-10-03) |
| Commit | DONE | PROVEN: 3 commits on `feat/tender-workbench`, pushed, draft PR https://github.com/supermhel/Tool/pull/1 . `main` untouched |
| Jev-style provider, vertical validation | OPEN | `ScoreProposer` is the plug-in point; demand still unvalidated |

## Open threads
- **Merge.** PR #1 is a draft; marking it ready and merging to `main` deploys production. That decision is the owner's.
- **Evaluator identity** is enforced only with API keys on (key label = evaluator). In open mode anyone can score as anyone.
- **Chain integrity** is tamper-evident, not tamper-proof; anchor the head hash externally for stronger guarantees. Concurrent writers are handled by compare-and-set; the Upstash path is proven only against a local HTTP fake.
- **Vertical validation.** Still a hypothesis. The free sensitivity calculator (`#sensitivity`) is the cheapest way to see whether strangers use it. No customer conversations have happened.
- **Jev / structured-output provider.** The `ScoreProposer` interface is the plug-in point; no provider other than rules and Ollama exists.
- **Untracked, left alone:** `.worktrees/t_dca4102f`, `AGENTS.md`, `CLAUDE.md`, `.claude/`.
