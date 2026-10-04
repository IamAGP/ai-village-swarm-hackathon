"""#41: for every flagged screen contradiction, extract the agent's NEXT screenshot after the paired turn.

The paired screenshot is captured right after its own turn's action (verified: typed text appears in it), so a final
Send/Publish click inside that turn may not have rendered yet. The next screenshot shows whether the state changed.
Writes /data/findings/claims_all/next/{next.jsonl, <claim8>.png}; one log line per flag; tars fetched per day, deleted.
"""
import json
import os
import sys
import time

import duckdb

sys.path.insert(0, '/opt/explorer')
from claims import members  # noqa: E402  per-day tar index (downloads to /data/claimtars)

D = '/data/findings/claims_all'
OUT = f'{D}/next'
WINDOW_MIN = 15


def log(m):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), m, flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    labels = {r['claim_id']: r for r in (json.loads(l) for l in open(f'{D}/labels_all.jsonl'))}
    flags = [json.loads(l) for l in open(f'{D}/contra_check.jsonl')]
    c = duckdb.connect()
    c.execute("CREATE VIEW t AS SELECT * FROM read_parquet('/data/parquet/turns_slim.parquet')")
    c.execute("CREATE VIEW m AS SELECT id, content FROM read_parquet('/data/parquet/chat_messages.parquet')")
    plan = []
    for f in flags:
        L = labels[f['claim_id']]
        agent, at, act = c.execute("SELECT agent_id, created_at, action FROM t WHERE id::VARCHAR = ?", [L['turn_id']]).fetchone()
        nxt = c.execute(f"""SELECT id::VARCHAR, created_at, pt_day, action FROM t WHERE agent_id = ? AND created_at > ?
                            AND created_at <= ? + INTERVAL {WINDOW_MIN} MINUTE AND action IS NOT NULL AND action <> 'bash'
                            AND NOT coalesce(screenshot_is_redacted, false) ORDER BY created_at LIMIT 12""", [agent, at, at]).fetchall()
        claim = c.execute("SELECT content FROM m WHERE id = ?", [f['claim_id']]).fetchone()[0]
        plan.append((f, L, act, at, nxt, claim))
    by_day = {}
    for p in plan:
        for tid, tat, day, _ in p[4]:
            by_day.setdefault(str(day)[:10], set()).add(tid)
    found = {}
    for day in sorted(by_day):
        path, idx = members(day)
        for tid in by_day[day]:
            if f'{tid}.png' in idx:
                off, size = idx[f'{tid}.png']
                with open(path, 'rb') as fh:
                    fh.seek(off)
                    found[tid] = fh.read(size)
        if os.path.exists(path):
            os.remove(path)
        log(f'DAY {day} wanted={len(by_day[day])} have={sum(t in found for t in by_day[day])}')
    with open(f'{OUT}/next.jsonl', 'w') as out:
        for f, L, act, at, nxt, claim in plan:
            hit = next(((tid, tat, a) for tid, tat, _, a in nxt if tid in found), None)
            rec = {'claim8': f['claim_id'][:8], 'claim_id': f['claim_id'], 'claim_at': L['claim_at'], 'claim': claim[:1500],
                   'paired_turn': L['turn_id'], 'paired_action': act, 'paired_at': str(at), 'acted_after': f['acted_after'],
                   'next_turn': hit[0] if hit else None, 'next_at': str(hit[1]) if hit else None, 'next_action': hit[2] if hit else None}
            if hit:
                open(f"{OUT}/{rec['claim8']}.png", 'wb').write(found[hit[0]])
            out.write(json.dumps(rec) + '\n')
            log(f"FLAG {rec['claim8']} paired={act} next={rec['next_at']} {'png' if hit else 'NO_NEXT'}")
    log('DONE')


if __name__ == '__main__':
    main()
