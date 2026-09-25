"""Feasibility: can we trace how an artifact spreads across AI Village agents and channels?

Artifacts: URLs (exact strings, so matches are unambiguous) and bash programs.
For each URL mentioned in chat by several agents: who mentioned it first, and when each other agent first
used it in each channel — chat, memory snapshot, model reasoning/output, executed action — with row ids.

Runs on the explorer box after build.py. Each step writes /data/analysis/<step>.json and is skipped
if that file exists. One timestamped log line per step.
"""
import json
import os
import sys
import time

import duckdb

DB, OUT, PQ = "/data/analysis.duckdb", "/data/analysis", "/data/parquet"
TABLES = ["agents", "chat_messages", "agent_memories", "computer_use_turns", "computer_use_sessions"]
# Same URL normalisation in every channel: extract, then strip trailing punctuation.
URL_RE = r"""https?://[^\s<>"'`)\]}|,\\]+"""
MIN_AGENTS = 4
TOP_TRACE = 40


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def urls_from(col):
    return f"list_transform(regexp_extract_all({col}, '{URL_RE}'), u -> rtrim(u, '.:;!?*'))"


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def step(name, fn, con):
    path = f"{OUT}/{name}.json"
    if os.path.exists(path):
        log(f"SKIP {name}")
        return
    t0 = time.time()
    result = fn(con)
    with open(path + ".tmp", "w") as f:
        json.dump(result, f, indent=1, default=str)
    os.replace(path + ".tmp", path)
    log(f"STEP {name} secs={time.time() - t0:.0f}")


def chat_urls(con):
    con.execute(f"""
        CREATE OR REPLACE TABLE a_chat_urls AS
        SELECT id AS row_id, agent_speaker_id AS agent_id, created_at, room_id, unnest({urls_from('content')}) AS url
        FROM chat_messages WHERE speaker_type = 'agent'""")
    con.execute(f"""
        CREATE OR REPLACE TABLE a_candidates AS
        SELECT url, count(DISTINCT agent_id) AS n_agents, count(*) AS n_msgs,
               min(created_at) AS first_at, arg_min(agent_id, created_at) AS first_agent,
               arg_min(row_id, created_at) AS first_row
        FROM a_chat_urls GROUP BY url HAVING count(DISTINCT agent_id) >= {MIN_AGENTS}""")
    return {"chat_url_mentions": con.execute("SELECT count(*) FROM a_chat_urls").fetchone()[0],
            "distinct_urls": con.execute("SELECT count(DISTINCT url) FROM a_chat_urls").fetchone()[0],
            "candidates": con.execute("SELECT count(*) FROM a_candidates").fetchone()[0],
            "agents_per_url_hist": rows(con, """SELECT n_agents, count(*) AS urls FROM a_candidates
                                               GROUP BY 1 ORDER BY 1""")}


def channel_urls(con):
    """First use of each candidate URL per agent in the other channels (one scan per channel)."""
    con.execute(f"""
        CREATE OR REPLACE TABLE a_mem_urls AS
        WITH x AS (SELECT id AS row_id, agent_id, created_at, unnest({urls_from('content')}) AS url FROM agent_memories)
        SELECT x.url, x.agent_id, min(x.created_at) AS first_at, arg_min(x.row_id, x.created_at) AS first_row, count(*) AS n
        FROM x JOIN a_candidates c USING (url) GROUP BY ALL""")
    log("  memories scanned")
    con.execute(f"""
        CREATE OR REPLACE TABLE a_act_urls AS
        WITH x AS (SELECT t.id AS row_id, s.agent_id, t.created_at,
                          unnest({urls_from("coalesce(t.agent_action->>'command', '') || ' ' || coalesce(t.agent_action->>'text', '')")}) AS url
                   FROM computer_use_turns t JOIN computer_use_sessions s ON s.id = t.session_id
                   WHERE t.agent_action IS NOT NULL)
        SELECT x.url, x.agent_id, min(x.created_at) AS first_at, arg_min(x.row_id, x.created_at) AS first_row, count(*) AS n
        FROM x JOIN a_candidates c USING (url) GROUP BY ALL""")
    log("  actions scanned")
    con.execute(f"""
        CREATE OR REPLACE TABLE a_rsn_urls AS
        WITH x AS (SELECT t.id AS row_id, s.agent_id, t.created_at, unnest({urls_from('t.agent_messages::VARCHAR')}) AS url
                   FROM computer_use_turns t JOIN computer_use_sessions s ON s.id = t.session_id)
        SELECT x.url, x.agent_id, min(x.created_at) AS first_at, arg_min(x.row_id, x.created_at) AS first_row, count(*) AS n
        FROM x JOIN a_candidates c USING (url) GROUP BY ALL""")
    log("  reasoning scanned")
    con.execute("""
        CREATE OR REPLACE TABLE a_chat_first AS
        SELECT url, agent_id, min(created_at) AS first_at, arg_min(row_id, created_at) AS first_row, count(*) AS n
        FROM a_chat_urls JOIN a_candidates USING (url) GROUP BY ALL""")
    return {t: con.execute(f"SELECT count(*), count(DISTINCT url) FROM {t}").fetchone()
            for t in ("a_chat_first", "a_mem_urls", "a_act_urls", "a_rsn_urls")}


def ranked(con):
    """Rank candidate URLs by cross-channel spread: agents that used the URL outside chat after its first chat mention."""
    return rows(con, f"""
        WITH ch AS (
          SELECT url, agent_id, 'chat' AS channel, first_at, first_row FROM a_chat_first
          UNION ALL SELECT url, agent_id, 'memory', first_at, first_row FROM a_mem_urls
          UNION ALL SELECT url, agent_id, 'action', first_at, first_row FROM a_act_urls
          UNION ALL SELECT url, agent_id, 'reasoning', first_at, first_row FROM a_rsn_urls)
        SELECT c.url, c.n_agents AS chat_agents, c.n_msgs AS chat_msgs, c.first_at, a.name AS first_agent,
               count(DISTINCT ch.agent_id) AS agents_any_channel,
               count(DISTINCT ch.agent_id) FILTER (WHERE ch.channel = 'memory')    AS agents_memory,
               count(DISTINCT ch.agent_id) FILTER (WHERE ch.channel = 'action')    AS agents_action,
               count(DISTINCT ch.agent_id) FILTER (WHERE ch.channel = 'reasoning') AS agents_reasoning,
               count(DISTINCT ch.agent_id) FILTER (WHERE ch.first_at > c.first_at
                                                    AND ch.agent_id <> c.first_agent) AS later_adopters
        FROM a_candidates c JOIN ch USING (url) LEFT JOIN agents a ON a.id::VARCHAR = c.first_agent
        GROUP BY ALL ORDER BY later_adopters DESC, agents_any_channel DESC LIMIT {TOP_TRACE}""")


def rows_param(con, url):
    cur = con.execute("""
        WITH ch AS (
          SELECT agent_id, 'chat' AS channel, first_at, first_row, n FROM a_chat_first WHERE url = ?
          UNION ALL SELECT agent_id, 'memory', first_at, first_row, n FROM a_mem_urls WHERE url = ?
          UNION ALL SELECT agent_id, 'action', first_at, first_row, n FROM a_act_urls WHERE url = ?
          UNION ALL SELECT agent_id, 'reasoning', first_at, first_row, n FROM a_rsn_urls WHERE url = ?)
        SELECT a.name AS agent, ch.channel, ch.first_at, ch.first_row, ch.n
        FROM ch LEFT JOIN agents a ON a.id::VARCHAR = ch.agent_id ORDER BY ch.first_at""", [url] * 4)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def bash_programs(con):
    """Adoption of command-line programs: first use per agent, for programs used by >= MIN_AGENTS agents."""
    return rows(con, f"""
        WITH x AS (
          SELECT s.agent_id, t.created_at, t.id AS row_id,
                 regexp_extract(trim(t.agent_action->>'command'), '^(?:sudo\\s+)?([A-Za-z0-9_./-]+)', 1) AS prog
          FROM computer_use_turns t JOIN computer_use_sessions s ON s.id = t.session_id
          WHERE t.agent_action->>'command' IS NOT NULL),
        f AS (SELECT prog, agent_id, min(created_at) AS first_at, arg_min(row_id, created_at) AS first_row, count(*) AS n
              FROM x WHERE prog <> '' GROUP BY ALL)
        SELECT prog, count(*) AS agents, sum(n) AS uses, min(first_at) AS first_at,
               arg_min(a.name, first_at) AS first_agent, max(first_at) AS last_adoption
        FROM f LEFT JOIN agents a ON a.id::VARCHAR = f.agent_id
        GROUP BY prog HAVING count(*) >= {MIN_AGENTS} ORDER BY agents DESC, uses DESC LIMIT 120""")


def main():
    os.makedirs(OUT, exist_ok=True)
    # Separate DB file: the dashboard keeps explorer.duckdb open, and DuckDB allows no writer alongside it.
    con = duckdb.connect(DB)
    for t in TABLES:
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")
    con.execute("SET memory_limit='20GB'; SET temp_directory='/data/tmp'; SET threads=4;"
                "SET preserve_insertion_order=false; SET TimeZone='UTC';")
    step("chat_urls", chat_urls, con)
    step("channel_urls", channel_urls, con)
    step("ranked", ranked, con)
    step("traces", lambda c: {u: rows_param(c, u) for u in
                              [r["url"] for r in json.load(open(f"{OUT}/ranked.json"))[:15]]}, con)
    step("bash_programs", bash_programs, con)
    log("FEASIBILITY DONE")


if __name__ == "__main__":
    sys.exit(main())
