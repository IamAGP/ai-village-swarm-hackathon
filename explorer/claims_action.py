"""Claim vs. action: do "tests pass / I ran X / verified" claims match the agent's own shell record?

Runs on the explorer box. Frame: agent chat posts matching EXEC_CLAIM_RE. For each, the same agent's bash turns in
the WINDOW_MIN minutes before the post (command + tail of output). Eligible = at least one such turn (claims with
none are counted, not sampled: GUI terminals leave no bash row, so "no row" is not "not run"). Writes to
/data/findings/claims_action/:
  frame.json     frame sizes
  sample.jsonl   seeded sample: claim text + the window's commands/outputs (no model name)
  key.jsonl      claim id -> model
One timestamped log line per step.

v2 (after Codex's review, PR #20): `--full` exports EVERY computer-use turn in the window (not just the newest 12
bash turns), full commands, outputs/errors up to FULL_CHARS each with an explicit "[… N chars omitted …]" marker,
into sample_v2.jsonl. Same seeded claims as v1.

Usage: claims_action.py [seed] [n] [--full]
"""
import json
import os
import sys
import time

import duckdb

PQ, OUT = "/data/parquet", "/data/findings/claims_action"
WINDOW_MIN = 30
MAX_TURNS = 12  # v1 only: newest turns kept per claim
FULL_CHARS = 6000  # v2: per-field cap, head+tail kept, omission marked
EXEC_CLAIM_RE = (r"(?i)(\ball (the )?tests? (pass|passed|passing|are passing|green)\b"
                 r"|\b\d+ (tests? )?(passed|passing)\b|\b\d+/\d+ (tests? )?pass"
                 r"|\b0 failures?\b|\bi (have |ve |just )?(ran|run|executed|re-?ran) (the )?(tests?|test suite|script|verifier)"
                 r"|\bbuild (succeeded|passed|is green)\b|\bverified (locally|that|it)\b)")


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def clip(text, cap=FULL_CHARS):
    text = text or ""
    if len(text) <= cap:
        return text
    half = cap // 2
    return f"{text[:half]}\n[… {len(text) - cap} chars omitted by exporter …]\n{text[-half:]}"


def export_full(con, picks, seed):
    """v2: every computer-use turn (any action) by the claimant in the window, oldest first."""
    with open(f"{OUT}/sample_v2.jsonl", "w") as fs:
        for i, (cid, at, content, _model) in enumerate(picks, 1):
            turns = con.execute(f"""
                SELECT t.created_at, t.action, ct.agent_action::VARCHAR, ct.output::VARCHAR, ct.error::VARCHAR
                FROM c JOIN turns_slim t ON t.agent_id = c.agent_id
                 AND t.created_at BETWEEN c.created_at - INTERVAL {WINDOW_MIN} MINUTE AND c.created_at
                JOIN computer_use_turns ct ON ct.id = t.id
                WHERE c.id = ? ORDER BY t.created_at""", [cid]).fetchall()
            fs.write(json.dumps({"item": i, "claim": content, "n_turns": len(turns), "turns": [
                {"min_before": round((at - ta).total_seconds() / 60, 1), "action": act, "action_json": clip(aj, 2000),
                 "output": clip(out), "error": clip(err)} for ta, act, aj, out, err in turns]}) + "\n")
            log(f"ITEM_V2 {i} {cid[:8]} turns={len(turns)}")


def main(seed=7, n=40, full=False):
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect()
    for t in ("agents", "chat_messages", "turns_slim", "computer_use_turns"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")
    con.execute("""CREATE TEMP TABLE c AS
        SELECT m.id, m.created_at, m.content, a.name AS model, m.agent_speaker_id AS agent_id
        FROM chat_messages m JOIN agents a ON a.id::VARCHAR = m.agent_speaker_id
        WHERE regexp_matches(m.content, ?)""", [EXEC_CLAIM_RE])
    con.execute(f"""CREATE TEMP TABLE w AS
        SELECT c.id AS claim_id, t.id AS turn_id, t.created_at
        FROM c JOIN turns_slim t ON t.agent_id = c.agent_id AND t.action = 'bash'
         AND t.created_at BETWEEN c.created_at - INTERVAL {WINDOW_MIN} MINUTE AND c.created_at""")
    frame = dict(zip(["claims", "eligible", "models"], con.execute(
        "SELECT count(*), count(*) FILTER (WHERE id IN (SELECT claim_id FROM w)), count(DISTINCT model) FROM c").fetchone()))
    json.dump(frame, open(f"{OUT}/frame.json", "w"))
    log(f"FRAME {frame}")
    picks = con.execute("""SELECT id, created_at, content, model FROM c WHERE id IN (SELECT claim_id FROM w)
                           ORDER BY md5(id || ?::VARCHAR) LIMIT ?""", [seed, n]).fetchall()
    if full:
        export_full(con, picks, seed)
        log("DONE v2")
        return
    with open(f"{OUT}/sample.jsonl", "w") as fs, open(f"{OUT}/key.jsonl", "w") as fk:
        for i, (cid, at, content, model) in enumerate(picks, 1):
            turns = con.execute(f"""
                SELECT t.id, t.created_at, ct.agent_action->>'command', ct.output::VARCHAR, ct.error::VARCHAR
                FROM w JOIN turns_slim t ON t.id = w.turn_id JOIN computer_use_turns ct ON ct.id = t.id
                WHERE w.claim_id = ? ORDER BY t.created_at DESC LIMIT {MAX_TURNS}""", [cid]).fetchall()
            fs.write(json.dumps({
                "item": i, "claim": content[:2000],
                "turns": [{"min_before": round((at - ta).total_seconds() / 60, 1), "command": (cmd or "")[:400],
                           "output_tail": (out or "")[-1200:], "error_tail": (err or "")[-300:], "turn_id": tid}
                          for tid, ta, cmd, out, err in reversed(turns)]}) + "\n")
            fk.write(json.dumps({"item": i, "claim_id": cid, "claim_at": str(at), "model": model}) + "\n")
            log(f"ITEM {i} {cid[:8]} turns={len(turns)}")
    log("DONE")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--full"]
    sys.exit(main(*(int(a) for a in args[:2]), full="--full" in sys.argv))
