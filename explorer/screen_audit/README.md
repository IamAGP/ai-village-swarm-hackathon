# Screen audit (claim vs. last screenshot), full frame

Runs on the explorer box; the screenshots never leave AWS.

1. `explorer/claims.py` with `CLAIMS_OUT=/data/findings/claims_all`, seed 11, n ≥ frame: the latest eligible
   screenshot before each of the 7,882 eligible completion claims (6,350 have one).
2. The box packs them into 26 batches of 250 (seed 20261002 shuffle) → `s3://…/_explorer/findings/shotbatches/`.
3. `prep_shots.py bNNN …` unpacks each batch into 5 chunk dirs of 50 (`/work/shots/bNNN_pK/`) with `RUBRIC.md`.
4. `trace_shots_all.sh` runs `trace_shots.sh <chunk>` 10 at a time. Each chunk is one headless Claude Code run
   (`claude -p`, model claude-opus-5-5) as an unprivileged `labeler` user, with tools limited to Read/Write/Edit
   (no shell, no web), so text inside a screenshot can't make it act. The subscription token is read from SSM
   (`/ai-village/claude-oauth-token`, SecureString) into the environment per run and is never printed or written
   to disk. One START/END log line per chunk, including token usage; labels are appended per image, so a
   killed run resumes where it stopped.
5. `explorer/shots_verify.py`: joins labels with claim metadata, then for every `contradicted` lists the agent's
   actions between the screenshot and the claim. A later action can mean the screen no longer reflects the state at
   claim time (pilot: 1 of 4 flags was fixed by later shell commands). Every reported contradiction is then
   checked by hand.

Pilot (batch 0, 5 local sub-agents): 83 supported / 4 flagged contradicted (2 confirmed, 1 partial, 1 overturned)
/ 94 unrelated / 69 unclear. EC2 test chunk: 50/50 in 154 s; two descriptions checked against the images by hand.
