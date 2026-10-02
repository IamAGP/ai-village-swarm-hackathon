"""Claim vs. screen: does an agent's "it's done / live / published" claim match the last screen it saw?

Runs on the explorer box. Draws a seeded uniform sample of chat completion claims that have a non-bash
computer-use turn by the same agent in the 10 minutes before the claim, and extracts that turn's screenshot
(the latest one present in the day's tar). Writes, incrementally, to /data/findings/claims/:
  sample.jsonl   one line per claim (claim id/text/time/model, turn id, minutes before claim)
  <claim8>.png   the screenshot
  key.jsonl      model names, kept apart from sample.jsonl so labelling can be blind to the model
One timestamped log line per claim. Tars are downloaded per day into /data/claimtars and deleted after use.

Usage: claims.py [seed] [n]   (CLAIMS_OUT=<dir> to write elsewhere; n >= frame size = every eligible claim)
"""
import json
import os
import subprocess
import sys
import tarfile
import time

import duckdb

PQ, TARS = "/data/parquet", "/data/claimtars"
OUT = os.environ.get("CLAIMS_OUT", "/data/findings/claims")  # full pass: /data/findings/claims_all
BUCKET_TARS = "s3://ai-village-459653581741/hf/ai-village/images/computer-use-turns"
LAST_TAR_DAY = "2026-08-21"  # tars end here (docs/DATA_PROFILE.md)
WINDOW_MIN = 10
# First-person or passive completion claims about publishing/sending/deploying something.
CLAIM_RE = (r"(?i)\b(is (now )?(live|deployed|published)"
            r"|(successfully|i'?ve|i have|just) (published|posted|deployed|submitted|sent|uploaded|launched|created)"
            r"|(has|have) been (published|posted|deployed|submitted|sent|uploaded|launched))\b")


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def sample(con, seed, n):
    for t in ("agents", "chat_messages", "turns_slim"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")
    return con.execute(f"""
        WITH c AS (
            SELECT m.id, m.created_at, m.content, a.name AS model, m.agent_speaker_id
            FROM chat_messages m JOIN agents a ON a.id::VARCHAR = m.agent_speaker_id
            WHERE regexp_matches(m.content, ?) AND m.created_at < TIMESTAMP '{LAST_TAR_DAY}' + INTERVAL 1 DAY),
        w AS (
            SELECT c.id, list(t.id ORDER BY t.created_at DESC) AS turn_ids,
                   list(t.created_at ORDER BY t.created_at DESC) AS turn_times,
                   list(t.pt_day ORDER BY t.created_at DESC) AS turn_days
            FROM c JOIN turns_slim t ON t.agent_id = c.agent_speaker_id
             AND t.created_at BETWEEN c.created_at - INTERVAL {WINDOW_MIN} MINUTE AND c.created_at
             AND t.action IS NOT NULL AND t.action <> 'bash' AND NOT coalesce(t.screenshot_is_redacted, false)
            GROUP BY c.id)
        SELECT c.id, c.created_at, c.content, c.model, w.turn_ids, w.turn_times, w.turn_days
        FROM c JOIN w USING (id)
        ORDER BY md5(c.id || ?::VARCHAR) LIMIT ?""", [CLAIM_RE, seed, n]).df()


def members(day):
    path = f"{TARS}/{day}.tar"
    if not os.path.exists(path):
        r = subprocess.run(["aws", "s3", "cp", "--quiet", f"{BUCKET_TARS}/{day}.tar", path + ".part",
                            "--region", "ap-south-1"], capture_output=True, text=True)
        if r.returncode != 0:
            log(f"TAR MISSING {day} {r.stderr.strip()[:200]}")
            return path, {}
        os.replace(path + ".part", path)
    with tarfile.open(path) as tf:
        return path, {m.name: (m.offset_data, m.size) for m in tf.getmembers()}


def main(seed=11, n=60):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TARS, exist_ok=True)
    df = sample(duckdb.connect(), seed, n)
    log(f"SAMPLE seed={seed} n={len(df)}")
    done = set()
    if os.path.exists(f"{OUT}/sample.jsonl"):  # resume: skip claims already written
        done = {json.loads(l)["claim_id"] for l in open(f"{OUT}/sample.jsonl")}
    # Group by the day of the newest candidate turn so each tar is fetched once.
    df["day"] = df.turn_days.map(lambda d: str(d[0])[:10])  # pandas may hand back a timestamp
    for day, g in df.sort_values("day").groupby("day"):
        todo = g[~g.id.isin(done)]
        if todo.empty:
            continue
        path, idx = members(day)
        for _, r in todo.iterrows():
            hit = next(((tid, tt) for tid, tt, td in zip(r.turn_ids, r.turn_times, r.turn_days)
                        if str(td)[:10] == day and f"{tid}.png" in idx), None)
            if hit:
                off, size = idx[f"{hit[0]}.png"]
                with open(path, "rb") as f:
                    f.seek(off)
                    png = f.read(size)
                with open(f"{OUT}/{r.id[:8]}.png", "wb") as f:
                    f.write(png)
            rec = {"claim_id": r.id, "claim_at": str(r.created_at), "claim": r.content[:1500],
                   "turn_id": hit[0] if hit else None,
                   "min_before": round((r.created_at - hit[1]).total_seconds() / 60, 1) if hit else None}
            with open(f"{OUT}/sample.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
            with open(f"{OUT}/key.jsonl", "a") as f:
                f.write(json.dumps({"claim_id": r.id, "model": r.model}) + "\n")
            log(f"CLAIM {r.id[:8]} day={day} model={r.model} shot={'yes' if hit else 'no'}")
        if os.path.exists(path):
            os.remove(path)
    log("CLAIMS DONE")


if __name__ == "__main__":
    sys.exit(main(*(int(a) for a in sys.argv[1:3])))
