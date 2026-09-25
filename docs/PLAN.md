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
- [ ] Filter noise artifacts (example.com, localhost, 127.0.0.1)
- [ ] Open question worth a finding: are spreading *claims* (e.g. Opus 5's disproofs) verified by anyone before amplification?

### Phase 2 — tracer core
- [ ] Artifact extraction + first-mention attribution
- [ ] Adoption edges across channels (chat, memory snapshot diff, bash/turn actions), each with evidence IDs
- [ ] Spread timeline / graph per artifact
- [ ] Coverage report (e.g. no screenshots after 2026-08-21; missing channels)

### Phase 3 — trust
- [ ] Hand-labeled sample (edges: real adoption vs coincidence)
- [ ] Precision / recall of the tracer on that sample
- [ ] Optional: outside-view test (public traces only vs internal ground truth)

### Phase 4 — interface + results
- [ ] Explorer page: "Trace" with one-click evidence
- [ ] 1–2 real findings written up with evidence links
- [ ] Re-sync dataset if upstream updates (expected Sun Sep 27 / Oct 4)

### Phase 5 — submission
- [ ] README + write-up (method, accuracy, limitations, findings)
- [ ] Short demo video
- [ ] Review journal/README for anything not to publish; make repo public at submission time
