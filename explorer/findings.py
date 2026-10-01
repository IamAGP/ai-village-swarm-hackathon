"""Precompute the small tables behind the story visualisations for Finding 1 (docs/FINDINGS.md).

Runs on the explorer box after tracer.py. Writes /data/findings/*.parquet:
  f1_moments   — key moments of the Graffiti.pc disproof cascade, each with the row id that proves it
  f1_verify    — every non-author execution of Opus 5's verify_conj*.py scripts, with success/fail
One timestamped log line per table.
"""
import os
import sys
import time

import duckdb

PQ, OUT = "/data/parquet", "/data/findings"
AUTHOR = "Claude Opus 5"
# Executed = a shell line invoking python on a verify_conj*.py file (docs/FINDINGS.md, *Method*).
EXEC_RE = r"(^|\n|&&|;|\|)\s*(timeout \d+\s+)?python3?\s+[^\n;&|]*verify_conj[0-9a-z_]*\.py"


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def write(con, name, sql):
    path = f"{OUT}/{name}.parquet"
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT parquet)")
    log(f"TABLE {name} rows={con.execute(f'SELECT count(*) FROM read_parquet(?)', [path]).fetchone()[0]}")


def main():
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect()
    for t in ("agents", "chat_messages", "computer_use_turns", "computer_use_sessions"):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")

    write(con, "f1_verify", f"""
        SELECT t.created_at, a.name AS agent, t.id AS row_id,
               regexp_extract(t.agent_action->>'command', 'verify_conj[0-9a-z_]*\\.py') AS script,
               CASE WHEN lower(t.output::VARCHAR) LIKE '%traceback%' OR lower(t.output::VARCHAR) LIKE '%error%'
                    THEN 'fail' ELSE 'success' END AS status
        FROM computer_use_turns t
        JOIN computer_use_sessions s ON s.id = t.session_id
        JOIN agents a ON a.id::VARCHAR = s.agent_id
        WHERE a.name <> '{AUTHOR}' AND regexp_matches(t.agent_action->>'command', '{EXEC_RE.replace("'", "''")}')""")

    # Key moments. Row-id prefixes come from docs/FINDINGS.md; the GLM-5.2 catch is located by content.
    write(con, "f1_moments", """
        SELECT created_at, 'Opus 5 announces the disproofs' AS label, id AS row_id, 'chat' AS kind
          FROM chat_messages WHERE id LIKE 'eb0a037a%'
        UNION ALL SELECT created_at, 'Grok 4.5 publishes a news article', id, 'turn'
          FROM computer_use_turns WHERE id LIKE '9500c361%'
        UNION ALL SELECT created_at, 'Coordinator orders a $19.99 Gumroad listing', id, 'chat'
          FROM chat_messages WHERE id LIKE 'd72e6672%'
        UNION ALL SELECT created_at, 'Gumroad blocks it: no payment method, 59-byte PDF', id, 'turn'
          FROM computer_use_turns WHERE id LIKE 'b6eb55fe%'
        UNION ALL SELECT min(m.created_at), 'GLM-5.2 flags a fabricated retelling', arg_min(m.id, m.created_at), 'chat'
          FROM chat_messages m JOIN agents a ON a.id::VARCHAR = m.agent_speaker_id
          WHERE a.name = 'GLM-5.2' AND m.content LIKE '%FABRICATED%'
            AND m.created_at BETWEEN TIMESTAMP '2026-07-30 17:50' AND TIMESTAMP '2026-07-30 18:10'
        UNION ALL SELECT created_at, 'First independent check (fails)', id, 'turn'
          FROM computer_use_turns WHERE id LIKE 'a5abb56d%'
        UNION ALL SELECT created_at, 'First successful independent check', id, 'turn'
          FROM computer_use_turns WHERE id LIKE '17ad5fe9%'
        UNION ALL SELECT created_at, 'News site: "18 disproofs verified in a single day"', id, 'turn'
          FROM computer_use_turns WHERE id LIKE '0bece99a%'
        ORDER BY 1""")
    log("FINDINGS DONE")


if __name__ == "__main__":
    sys.exit(main())
