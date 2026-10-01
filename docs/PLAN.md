# Hackathon plan — evidence-linked swarm tracer

Hackathon: AI Swarm Dynamics (AI Village × Grove Research), Oct 3–4 2026, online.
Submission deadline: **Sun Oct 4, 9:00 PM PT (Mon Oct 5, 09:30 IST)** — repo + short write-up/video (+ optional real results).

**Thesis** (from METR HF-incident report pp.24–28, 58, 83; arXiv 2609.04170 §4; collusion.wiki):
swarm investigations are bottlenecked on manual log reading, and AI-assisted analysis is hard to trust
because findings are not linked to evidence or measured. Build a tracer whose every claim cites raw rows,
whose accuracy is measured on a labeled sample, and which reports what the data cannot show.

## Checklist

### Phase 0 — groundwork
- [x] Mirror dataset to S3 (390 files, 176.87 GB, rev 838b415) — 2026-09-22
- [x] Profile data → `docs/DATA_PROFILE.md` — 2026-09-23
- [x] Explorer (Streamlit + DuckDB) on EC2 via SSM port-forward — 2026-09-23
- [x] Read sources: METR HF report, arXiv 2609.04170, collusion.wiki — 2026-09-26
- [ ] Rotate HF token `ai-village` (user action)

### Phase 1 — feasibility (is spread traceable in AI Village?)
- [x] Candidate spread events from URLs — 209 URLs mentioned in chat by ≥4 agents, all seen in memory/action/
      reasoning channels (`explorer/feasibility.py`, 2026-09-26). Bash-program adoption also computed.
- [x] Hand-check: `graffiti-verification` — Opus 5 chat eb0a037a (18:53:39) → Grok 4.5 turn 9500c361 (18:57:17,
      "Building desk 2178 on Opus 5's … disproofs") → Grok/DeepSeek-V4 news posts (18:57/18:58). Causal, row-verified.
      YouTube short: GPT-5.2 memory → chat 3c9c1052 → GLM-5.2 action same minute → 10+ memories.
- [x] **GO** on the tracer.
- [ ] Separate broadcast (organizer/system-prompt URLs, e.g. theaidigest.org/village) from peer contagion
- [x] Filter noise artifacts (localhost, 127.0.0.1, example.*, templated URLs) — flagged `origin=noise`
- [x] Finding: Graffiti.pc disproof cascade — re-broadcast ~4 min, attempted paid product ~22 h (blocked by payment wall), first successful independent
      verification ~26.5 h; fabricated retelling caught by GLM-5.2 → `docs/FINDINGS.md`

### Phase 2 — tracer core
- [x] Artifact extraction + first-use attribution — `explorer/tracer.py`: 5.43M URL uses, 19,376 URLs with ≥2 agents
- [x] Canonical URLs (www/m, http, .git, youtu.be/shorts/watch, #fragment) — v2; effect small (none 49.5→48.9%)
- [x] Exposure edges with evidence (explicit / temporal / stale / none) — 73,824 edges; explicit 4.6%, median lag 2.2 min
- [x] Origin labels (agent_created / agent_chat / human / broadcast_suspect / organizer / noise)
- [x] Spread timeline + edge inspector — explorer **Trace** page, linkable via `?url=` (AppTest: 0 exceptions,
      graffiti trace renders Grok 4.5 ← Opus 5 explicit 4 min with both rows)
- [x] "Mentioned by name" evidence (v4): 4,295 edges (5.8%) move from `none` (48.9→43.1%); broadcast_suspect 318→214;
      median lag 7.3 min. Measured twice (v4, v5 fresh): ~21–26% wrong → kept as low-confidence level, not headline.
- [ ] Coverage report (e.g. no screenshots after 2026-08-21; missing channels)

### Phase 3 — trust
- [x] Blind-labelled samples: v2 (seed 3) and held-out v3 (seed 777), two model annotators, κ = 0.84 → `docs/EVAL.md`
- [x] v3 fix (prefer the prior poster the adopter names): 0 wrong edges in 50 held-out sourced edges (v2: 3/44)
- [ ] Human spot-check of ~10 labelled items (user)
- [x] Precision with Wilson CIs: explicit strict ~56–60%, lenient 100% [87–100%]; misses among `none` 0/22 decided
- [ ] Optional: outside-view test (public traces only vs internal ground truth)

- [ ] Future: exclude filename/domain slugs from `mention`, re-measure on a fresh sample

### Phase 4 — interface + results
- [ ] Explorer page: "Trace" with one-click evidence
- [~] Findings with evidence links — 1 written (`docs/FINDINGS.md`); aim for 1 more
- [ ] Re-sync dataset if upstream updates (expected Sun Sep 27 / Oct 4)

### Phase 5 — submission
- [ ] README + write-up (method, accuracy, limitations, findings)
- [ ] Short demo video
- [ ] Review journal/README for anything not to publish; make repo public at submission time
