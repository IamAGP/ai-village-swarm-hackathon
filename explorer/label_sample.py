"""Draw a stratified sample of tracer edges for accuracy labelling, with the evidence text of both sides.

Output: /data/trace/label_sample.jsonl — one edge per line with source/target excerpts (±400 chars
around the URL). Labels are added afterwards (label.jsonl) and scored by score_labels.py.
Seeded, so the sample is reproducible.
"""
import json
import sys

import duckdb

T, P = "/data/trace", "/data/parquet"
PER_STRATUM = {"explicit": 25, "temporal": 25, "none": 15}
SEED = 20261003


def excerpt(text, url, width=400):
    if not text:
        return None
    keys = [url, url.split("://", 1)[-1], url.split("v=")[-1] if "youtube.com/watch" in url else url.rsplit("/", 1)[-1]]
    i = next((text.find(k) for k in keys if k and text.find(k) >= 0), -1)
    if i < 0:
        return text[: 2 * width]
    return ("…" if i > width else "") + text[max(0, i - width): i + width] + "…"


def main(seed=SEED, name="label_sample"):
    con = duckdb.connect()
    con.execute(f"SELECT setseed({(seed % 1000) / 1000})")
    for v in ("agents", "chat_messages", "computer_use_turns", "agent_memories"):
        con.execute(f"CREATE VIEW {v} AS SELECT * FROM read_parquet('{P}/{v}.parquet')")
    con.execute(f"CREATE VIEW edges AS SELECT * FROM read_parquet('{T}/trace_edges_scored.parquet')")
    con.execute(f"CREATE VIEW art AS SELECT * FROM read_parquet('{T}/trace_artifacts.parquet')")
    names = dict(con.execute("SELECT id::VARCHAR, name FROM agents").fetchall())
    out = open(f"{T}/{name}.jsonl", "w")
    n = 0
    for stratum, k in PER_STRATUM.items():
        rows = con.execute(f"""
            SELECT e.*, a.origin FROM edges e JOIN art a USING (url)
            WHERE e.evidence = ? AND a.origin <> 'noise' AND e.target_channel IN ('chat', 'action', 'model_output')
            ORDER BY random() LIMIT {k}""", [stratum]).fetchall()
        cols = [d[0] for d in con.description]
        for r in rows:
            e = dict(zip(cols, r))
            src = con.execute("SELECT content FROM chat_messages WHERE id = ?", [e["source_row"]]).fetchone() if e["source_row"] else None
            if e["target_channel"] == "chat":
                tgt = con.execute("SELECT content FROM chat_messages WHERE id = ?", [e["target_row"]]).fetchone()
            else:
                tgt = con.execute("SELECT agent_action::VARCHAR || ' ' || agent_messages::VARCHAR FROM computer_use_turns WHERE id = ?",
                                  [e["target_row"]]).fetchone()
            rec = {"stratum": stratum, "url": e["url"], "origin": e["origin"],
                   "source": names.get(e["source"], e["source"]), "target": names.get(e["target"], e["target"]),
                   "target_channel": e["target_channel"], "lag_s": e["lag_s"], "prior_posts": e["prior_posts"],
                   "source_row": e["source_row"], "target_row": e["target_row"],
                   "source_text": excerpt(src[0], e["url"]) if src else None,
                   "target_text": excerpt(tgt[0], e["url"]) if tgt else None}
            out.write(json.dumps(rec, default=str) + "\n")
            n += 1
    out.close()
    print(f"sampled {n} edges")


if __name__ == "__main__":
    # usage: label_sample.py [seed] [name]  (a new seed gives a held-out sample)
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else SEED, sys.argv[2] if len(sys.argv) > 2 else "label_sample"))
