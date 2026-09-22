# AI Village — AI Swarm Dynamics Hackathon

Work for the [AI Village × Grove Research AI Swarm Dynamics Hackathon](https://swarmchasing.com)
(Oct 3–4, 2026): tools to understand, trace, and investigate multi-agent (swarm) behaviour.

## Data

Built on the gated [AI Village dataset](https://huggingface.co/datasets/aidigestorg/ai-village)
by AI Digest. The dataset is **not** redistributed here. A private mirror lives in S3:

| | |
|---|---|
| Location | `s3://ai-village-459653581741/hf/ai-village/` (ap-south-1, private) |
| Revision | `838b4150303ca8228e8edb432d8b8ccae353d258` (HF commit 2026-09-20) |
| Contents | 390 files, 176,865,369,812 bytes: 13 JSONL tables + 369 daily screenshot tars |

Upstream refreshes roughly weekly (Sundays ~14:00 UTC). `infra/transfer.sh` re-syncs a
revision into S3, skipping files already present with the same size.

**Terms of use:** research and analysis only; no training or fine-tuning AI systems on this
data without AI Digest's written permission; no re-identification of individuals; cite
AI Digest / AI Village.

> AI Digest, "AI Village dataset", 2026. https://theaidigest.org/village

## Layout

```
infra/transfer.sh   HF → S3 mirror (runs as EC2 user data; resumable, self-terminating)
logs/               logs from the three mirror passes
JOURNAL.md          experiment journal: preflight answers, decisions, costs, mistakes
```
