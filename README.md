# Evidence-linked swarm tracer — AI Village

For the [AI Village × Grove Research AI Swarm Dynamics Hackathon](https://swarmchasing.com) (Oct 3–4, 2026).

**Problem.** Investigations of agent swarms are bottlenecked on reading logs by hand, and AI-assisted
analysis is hard to trust. METR's OpenAI/Hugging Face incident report: analysis agents "had significantly
worse judgment and reliability … challenging to spot check" (p.24), anecdotes "we were not able to … manually
verify" (p.27). DeepMind's cheating-swarm case study (arXiv 2609.04170): "oversight becomes the bottleneck".
The German Wiki investigators (collusion.wiki) had no transcripts at all.

**What this is.** A tracer that follows artifacts (URLs) as they spread between ~46 AI agents across four
channels — chat, memory snapshots, model output, executed actions — and draws an *exposure edge* for every
adoption, where **every edge cites the two dataset rows it rests on**, carries an evidence level, and the
evidence levels have **measured precision** on blind-labelled samples.

| evidence | meaning | held-out precision (strict / lenient) |
|---|---|---|
| `explicit` | the adopter's first use names the source agent | ~56–60% / 100% [87–100%] |
| `temporal` | the source posted the URL in chat ≤ 72 h before | ~32–40% / 100% [87–100%] |
| `mention` | no URL post, but the source named it (URL slug) in chat ≤ 72 h before | not yet measured |
| `stale` / `none` | older post / no visible source | misses among `none`: 0/22 decided |

Details: [`docs/EVAL.md`](docs/EVAL.md). A worked investigation: [`docs/FINDINGS.md`](docs/FINDINGS.md) —
in one cascade, claims were re-broadcast in ~4 minutes and sold as a product within ~22 h, while the first
successful independent verification came after ~26.5 h; a fabricated retelling was caught by a peer agent.

## Running it

Everything runs on a private EC2 box next to the data (the gated data never leaves AWS):

```
explorer/build.py        JSONL → typed Parquet + slim tables (bash actions, provider shape, PT day)
explorer/profile.py      aggregate-only data profile → docs/DATA_PROFILE.md
explorer/tracer.py       URL uses → first uses → adoptions → scored exposure edges → artifact origins
explorer/label_sample.py stratified, seeded edge sample for blind labelling
explorer/app.py          Streamlit explorer: Overview, Trace (?url=…), Agent, Session replay, Chat, Day, SQL
explorer/connect.sh      start the box if stopped + SSM port-forward → http://localhost:8501
infra/                   S3 mirror script (HF → S3 via hf_xet) and box bootstrap (idle watchdog)
```

## Data

Built on the gated [AI Village dataset](https://huggingface.co/datasets/aidigestorg/ai-village) by AI Digest,
revision `838b4150303ca8228e8edb432d8b8ccae353d258` (2026-09-20). The dataset is **not** redistributed here;
a private mirror lives in S3 (390 files, 176,865,369,812 bytes). Measured shape and traps:
[`docs/DATA_PROFILE.md`](docs/DATA_PROFILE.md).

**Terms of use:** research and analysis only; no training or fine-tuning AI systems on this data without
AI Digest's written permission; no re-identification of individuals; cite AI Digest / AI Village.

> AI Digest, "AI Village dataset", 2026. https://theaidigest.org/village

Process log (decisions, costs, mistakes): [`JOURNAL.md`](JOURNAL.md) · plan: [`docs/PLAN.md`](docs/PLAN.md).
