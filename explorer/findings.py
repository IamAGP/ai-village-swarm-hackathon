"""Precompute the small tables behind the story visualisations for Finding 1 (docs/FINDINGS.md).

Runs on the explorer box after tracer.py. Writes /data/findings/*.parquet:
  f1_moments   — key moments of the Graffiti.pc disproof cascade, each with the row id that proves it
  f1_verify    — non-author turns invoking a verify_conj*.py filename (one row per turn; the file is not
                 provenance-checked), with status fail / success / unknown
One timestamped log line per table.
"""
import os
import re
import sys
import time

import duckdb

PQ, OUT = "/data/parquet", "/data/findings"
AUTHOR = "Claude Opus 5"
# Executed = a shell line invoking python on a verify_conj*.py file (docs/FINDINGS.md, *Method*).
EXEC_RE = r"(^|\n|&&|;|\|)\s*(timeout \d+\s+)?python3?\s+[^\n;&|]*verify_conj[0-9a-z_]*\.py"
# Text that is written, not run: heredoc bodies and quoted strings. Without stripping these, EXEC_RE matched a
# news article that *quotes* "git clone && python3 verify/verify_conj605.py" (turn 0bece99a).
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?(\n\s*\1\b|\Z)", re.S)
QUOTED_RE = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"", re.S)


def executes_verifier(cmd):
    return bool(cmd) and re.search(EXEC_RE, QUOTED_RE.sub("''", HEREDOC_RE.sub("", cmd))) is not None


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

    # Candidates by SQL regex, then drop matches that only occur inside heredocs / quoted strings.
    cand = con.execute(f"""
        SELECT t.created_at, a.name AS agent, t.id AS row_id, t.agent_action->>'command' AS cmd,
               regexp_extract(t.agent_action->>'command', 'verify_conj[0-9a-z_]*\\.py') AS script,
               -- Three states (Codex review, PR #20): an error signal, a success signal, or neither (incl. no output).
               -- Signals are keyword heuristics on tool output, not mathematical verification.
               CASE WHEN regexp_matches(lower(t.output::VARCHAR), 'traceback|error')                     THEN 'fail'
                    WHEN regexp_matches(lower(t.output::VARCHAR), 'pass|verified|assert|exit 0|exit code 0') THEN 'success'
                    ELSE 'unknown' END AS status
        FROM computer_use_turns t
        JOIN computer_use_sessions s ON s.id = t.session_id
        JOIN agents a ON a.id::VARCHAR = s.agent_id
        WHERE a.name <> '{AUTHOR}' AND regexp_matches(t.agent_action->>'command', ?)""", [EXEC_RE]).df()
    keep = cand.cmd.map(executes_verifier)
    for _, r in cand[~keep].iterrows():
        log(f"DROPPED written-not-run {r.row_id[:8]} {r.agent} {r.created_at}")
    con.register("f1_verify_df", cand[keep].drop(columns="cmd"))
    write(con, "f1_verify", "SELECT * FROM f1_verify_df")

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
        UNION ALL SELECT created_at, 'First independent check with a success signal', id, 'turn'
          FROM computer_use_turns WHERE id LIKE '17ad5fe9%'
        UNION ALL SELECT created_at, 'News site: "18 disproofs verified in a single day"', id, 'turn'
          FROM computer_use_turns WHERE id LIKE '0bece99a%'
        ORDER BY 1""")
    log("FINDINGS DONE")


if __name__ == "__main__":
    sys.exit(main())
