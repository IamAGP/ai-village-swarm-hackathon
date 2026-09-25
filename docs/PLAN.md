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
- [ ] Candidate spread events from distinctive artifacts (URLs, coined terms, novel bash commands):
      first agent + time → later adopters in chat, memories, actions
- [ ] Hand-check 2–3 candidates end to end (chat → memory → action) with row IDs
- [ ] Go / no-go on the tracer; if no-go, fall back to norm-enforcement miner

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
