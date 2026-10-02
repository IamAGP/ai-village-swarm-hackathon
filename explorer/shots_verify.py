"""Collect the screen-audit labels and check every `contradicted` against what the agent did next.

Runs on the explorer box after trace_shots_all.sh. For each item labelled contradicted, lists every
computer-use turn by the same agent between the screenshot and the claim (action + output tail), and flags
`acted_after` when any non-chat action happened in between (the screen may no longer reflect the state at
claim time, e.g. a failed merge fixed by a later shell command). Writes /data/findings/claims_all/
  labels_all.jsonl   every label joined with claim id / model / times (no claim text)
  contra_check.jsonl one record per contradicted item with the intervening turns
One timestamped log line per step.
"""
import glob, json, time
import duckdb

D, W = "/data/findings/claims_all", "/work/shots"


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def main():
    sample = {json.loads(l)["claim_id"][:8]: json.loads(l) for l in open(f"{D}/sample.jsonl")}
    key = {json.loads(l)["claim_id"][:8]: json.loads(l)["model"] for l in open(f"{D}/key.jsonl")}
    labels = []
    for f in sorted(glob.glob(f"{W}/b*_p*/labels.jsonl")):
        for line in open(f):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                log(f"BAD LINE {f}"); continue
            s = sample.get(r.get("item"))
            if not s:
                log(f"UNKNOWN ITEM {r.get('item')} in {f}"); continue
            labels.append({**r, "chunk": f.split("/")[-2], "claim_id": s["claim_id"], "claim_at": s["claim_at"],
                           "turn_id": s["turn_id"], "min_before": s["min_before"], "model": key.get(r["item"])})
    with open(f"{D}/labels_all.jsonl", "w") as out:
        for r in labels:
            out.write(json.dumps(r) + "\n")
    log(f"LABELS {len(labels)} distinct={len({r['item'] for r in labels})}")

    con = duckdb.connect()
    for t in ("turns_slim", "computer_use_turns"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('/data/parquet/{t}.parquet')")
    n = 0
    with open(f"{D}/contra_check.jsonl", "w") as out:
        for r in labels:
            if r.get("label") != "contradicted":
                continue
            agent, shot_at = con.execute("SELECT agent_id, created_at FROM turns_slim WHERE id = ?", [r["turn_id"]]).fetchone()
            rows = con.execute("""
                SELECT t.created_at, t.action, left(coalesce(ct.agent_action::VARCHAR, ''), 300),
                       right(coalesce(ct.output::VARCHAR, ''), 300)
                FROM turns_slim t JOIN computer_use_turns ct ON ct.id = t.id
                WHERE t.agent_id = ? AND t.created_at > ? AND t.created_at <= CAST(? AS TIMESTAMP)
                ORDER BY 1""", [agent, shot_at, r["claim_at"]]).fetchall()
            acted = [x for x in rows if x[1] not in ("send_message_back_to_chat", None)]
            out.write(json.dumps({"item": r["item"], "claim_id": r["claim_id"], "model": r["model"],
                                  "screen": r.get("screen"), "acted_after": bool(acted), "n_after": len(rows),
                                  "after": [[str(a), b, c, d] for a, b, c, d in rows]}) + "\n")
            n += 1
    log(f"CONTRADICTED {n}")


if __name__ == "__main__":
    main()
