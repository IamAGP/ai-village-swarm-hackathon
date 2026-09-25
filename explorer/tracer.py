"""Evidence-linked spread tracer for AI Village (URL artifacts).

For every URL used by >= 2 agents, across four channels (chat, memory snapshots, model output, executed
actions), this derives:
  trace_first_use  — each agent's first use of the URL per channel, with the row id that proves it
  trace_edges      — for each adopting agent, the most recent prior public (chat) post of the URL by someone
                     else = its likely exposure, with an evidence level:
                       explicit   adopter's first-use text names the source agent
                       temporal   a prior chat post exists within WINDOW before the adoption
                       stale      a prior chat post exists, but older than WINDOW
                       none       no prior public post (independent discovery, or a channel we cannot see)
  trace_artifacts  — per URL: origin (human / organizer / agent-created / agent-chat / broadcast-suspect),
                     reach, evidence mix, noise flag

Runs on the explorer box; writes /data/trace/*.parquet. Idempotent per output file. One log line per step.
"""
import os
import sys
import time

import duckdb

DB, PQ, OUT = "/data/trace.duckdb", "/data/parquet", "/data/trace"
TABLES = ["agents", "chat_messages", "agent_memories", "computer_use_turns", "computer_use_sessions",
          "events_slim", "village_goals", "agent_goals"]
URL_RE = r"""https?://[^\s<>"'`)\]}|,\\]+"""
WINDOW_HOURS = 72
# Bare-name mentions are weaker than URL posts; a blind sample (2026-09-26) had every correct mention edge
# under 2 min and half the wrong ones over 3 h, so they get a much shorter window.
MENTION_WINDOW_MIN = 60
BROADCAST_AGENTS, BROADCAST_MINUTES = 5, 60
NOISE_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "example.com", "example.org", "example.net")


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def canonical(u):
    """Canonical URL so spelling variants of one artifact match (first tracer run showed
    `repo` vs `repo.git`, m./www., http/https and youtu.be/shorts/watch splitting one artifact into several)."""
    u = f"rtrim(split_part({u}, '#', 1), '.:;!?*')"
    u = f"regexp_replace({u}, '^http://', 'https://')"
    u = f"regexp_replace({u}, '^https://(www|m|mobile)\\.', 'https://')"
    u = (f"regexp_replace({u}, '^https://(youtube\\.com/(shorts/|watch\\?v=|live/)|youtu\\.be/)([A-Za-z0-9_-]{{11}}).*$', "
         f"'https://youtube.com/watch?v=\\3')")
    u = f"regexp_replace({u}, '\\.git$', '')"
    return f"rtrim({u}, '/')"


def urls_from(col):
    """Extract and canonicalise URLs identically in every channel."""
    pattern = URL_RE.replace("'", "''")
    return f"list_transform(regexp_extract_all({col}, '{pattern}'), u -> {canonical('u')})"


def build(con, name, sql):
    path = f"{OUT}/{name}.parquet"
    if not os.path.exists(path):
        t0 = time.time()
        con.execute(f"COPY ({sql}) TO '{path}.tmp' (FORMAT parquet, COMPRESSION zstd)")
        os.replace(f"{path}.tmp", path)
        n = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
        log(f"TABLE {name} rows={n} secs={time.time() - t0:.0f}")
    else:
        log(f"SKIP {name}")
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{path}')")


def main():
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect(DB)
    con.execute("SET memory_limit='20GB'; SET temp_directory='/data/tmp'; SET threads=4;"
                "SET preserve_insertion_order=false; SET TimeZone='UTC';")
    for t in TABLES:
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_parquet('{PQ}/{t}.parquet')")

    # 1. Every URL use, per channel, with the row that proves it.
    build(con, "trace_uses", f"""
        WITH chat AS (
          SELECT 'chat' AS channel, m.id AS row_id, m.created_at, m.room_id,
                 m.agent_speaker_id AS agent_id,
                 CASE WHEN m.speaker_type = 'user' THEN 'human:' || coalesce(e.speaker_name, m.user_speaker_id) END AS human,
                 unnest({urls_from('m.content')}) AS url
          FROM chat_messages m LEFT JOIN events_slim e ON e.message_id = m.id AND e.action_type = 'USER_TALK'),
        mem AS (
          SELECT 'memory', id, created_at, NULL, agent_id, NULL, unnest({urls_from('content')}) FROM agent_memories),
        turns AS (
          SELECT t.id, t.created_at, s.agent_id, t.agent_action, t.agent_messages
          FROM computer_use_turns t JOIN computer_use_sessions s ON s.id = t.session_id),
        act AS (
          SELECT 'action', id, created_at, NULL, agent_id, NULL,
                 unnest({urls_from("coalesce(agent_action->>'command', '') || ' ' || coalesce(agent_action->>'text', '')")})
          FROM turns WHERE agent_action IS NOT NULL),
        outp AS (
          SELECT 'model_output', id, created_at, NULL, agent_id, NULL, unnest({urls_from('agent_messages::VARCHAR')})
          FROM turns)
        SELECT * FROM chat UNION ALL SELECT * FROM mem UNION ALL SELECT * FROM act UNION ALL SELECT * FROM outp""")

    # 2. First use per (url, actor, channel); actor = agent id or 'human:<name>'.
    build(con, "trace_first_use", """
        SELECT url, coalesce(agent_id, human) AS actor, agent_id IS NULL AS is_human, channel,
               min(created_at) AS first_at, arg_min(row_id, created_at) AS row_id,
               arg_min(room_id, created_at) AS room_id, count(*) AS n
        FROM trace_uses WHERE url IS NOT NULL AND length(url) > 10
        GROUP BY ALL""")

    # 3. Artifacts: URLs used by >= 2 distinct agents in any channel.
    noise = ", ".join(f"'{h}'" for h in NOISE_HOSTS)
    build(con, "trace_artifacts_base", f"""
        WITH per AS (
          SELECT url, count(DISTINCT actor) FILTER (WHERE NOT is_human) AS n_agents,
                 count(DISTINCT actor) FILTER (WHERE is_human) AS n_humans,
                 min(first_at) AS first_at, arg_min(actor, first_at) AS first_actor,
                 arg_min(channel, first_at) AS first_channel, arg_min(row_id, first_at) AS first_row
          FROM trace_first_use GROUP BY url)
        SELECT *, lower(regexp_extract(url, '^https?://([^/:?#]+)', 1)) AS host
        FROM per WHERE n_agents >= 2""")
    con.execute(f"""CREATE OR REPLACE TEMP VIEW trace_art AS
                    SELECT *, host IN ({noise}) OR host LIKE '%.local' OR NOT contains(host, '.') OR url LIKE '%{{%' OR url LIKE '%$%' AS is_noise
                    FROM trace_artifacts_base""")

    # 4. Adoptions: an agent's earliest use of the URL in any channel, with its normalised text
    #    (chat / action / model output; memory snapshots name many agents, so they are not used for attribution).
    build(con, "trace_adopt", """
        WITH adopt AS (
          SELECT f.url, f.actor AS target, min(f.first_at) AS t_at,
                 arg_min(f.row_id, f.first_at) AS target_row, arg_min(f.channel, f.first_at) AS target_channel
          FROM trace_first_use f JOIN trace_art a USING (url)
          WHERE NOT f.is_human AND NOT a.is_noise GROUP BY ALL)
        SELECT d.*, CASE WHEN d.target_channel <> 'memory' THEN
                 ' ' || regexp_replace(lower(coalesce(cm.content, t.agent_action::VARCHAR || ' ' || t.agent_messages::VARCHAR, '')),
                                       '[^a-z0-9.-]+', ' ', 'g') || ' ' END AS target_text
        FROM adopt d
        LEFT JOIN chat_messages cm ON d.target_channel = 'chat' AND cm.id = d.target_row
        LEFT JOIN computer_use_turns t ON d.target_channel IN ('action', 'model_output') AND t.id = d.target_row""")

    # 4b. Name mentions: agents often refer to a repo/site by name without posting its URL. Slug = the URL's last
    #     path segment when it looks like a coined identifier (>= 8 chars, contains '-' or '_').
    #     Chat is tokenised once and hash-joined (a per-adoption substring scan would be ~10^10 comparisons).
    build(con, "trace_slug_mentions", """
        WITH slugs AS (
          SELECT DISTINCT url, lower(regexp_extract(url, '/([A-Za-z0-9_.-]+)$', 1)) AS slug FROM trace_adopt),
        good AS (SELECT * FROM slugs WHERE length(slug) >= 8 AND (contains(slug, '-') OR contains(slug, '_'))),
        tok AS (
          SELECT m.id AS row_id, m.created_at, m.room_id, coalesce(m.agent_speaker_id, 'human:' || m.user_speaker_id) AS actor,
                 unnest(list_distinct(regexp_extract_all(lower(m.content), '[a-z0-9][a-z0-9_.-]{6,}[a-z0-9]'))) AS token
          FROM chat_messages m)
        SELECT g.url, t.actor, t.created_at, t.row_id, t.room_id
        FROM good g JOIN tok t ON t.token = g.slug""")

    # 5. Exposure edge per adoption. Candidates = every other actor who posted the URL in chat before the
    #    adoption (their latest such post). If the adopter's text names candidates, the most recent NAMED one is
    #    the source (explicit); otherwise the most recent poster (temporal / stale). v2 picked only the most recent
    #    poster, and blind labels showed 3/22 temporal edges credited to the wrong agent that way (2026-09-26).
    build(con, "trace_edges_scored", f"""
        WITH names AS (
          -- Token-normalised aliases: "Claude Opus 5" -> ["claude opus 5", "opus 5"]; matched on word
          -- boundaries so "gpt-5" does not match "gpt-5.2" and "opus 5's" still matches "opus 5".
          SELECT id::VARCHAR AS agent_id,
                 list_distinct(list_transform([name, replace(name, 'Claude ', '')],
                     x -> trim(regexp_replace(lower(x), '[^a-z0-9.-]+', ' ', 'g')))) AS aliases
          FROM agents),
        posts AS (
          SELECT url, coalesce(agent_id, human) AS actor, created_at, row_id, room_id
          FROM trace_uses WHERE channel = 'chat'),
        cand AS (
          SELECT d.url, d.target, p.actor AS source, max(p.created_at) AS s_at,
                 arg_max(p.row_id, p.created_at) AS source_row, arg_max(p.room_id, p.created_at) AS source_room
          FROM trace_adopt d JOIN posts p ON p.url = d.url AND p.created_at < d.t_at AND p.actor <> d.target
          GROUP BY ALL),
        scored AS (
          SELECT c.*, d.target_text IS NOT NULL AND len(list_filter(coalesce(n.aliases, []), x -> length(x) >= 4 AND
                   (contains(d.target_text, ' ' || x || ' ') OR contains(d.target_text, ' ' || x || '. ')))) > 0 AS named
          FROM cand c JOIN trace_adopt d USING (url, target) LEFT JOIN names n ON n.agent_id = c.source),
        ranked AS (
          SELECT *, row_number() OVER (PARTITION BY url, target ORDER BY named DESC, s_at DESC) AS rk,
                 count(*) OVER (PARTITION BY url, target) AS prior_posters,
                 count(*) FILTER (WHERE named) OVER (PARTITION BY url, target) AS named_posters
          FROM scored)
        , mention AS (
          SELECT d.url, d.target, mm.actor AS source, max(mm.created_at) AS s_at,
                 arg_max(mm.row_id, mm.created_at) AS source_row, arg_max(mm.room_id, mm.created_at) AS source_room
          FROM trace_adopt d JOIN trace_slug_mentions mm
            ON mm.url = d.url AND mm.created_at < d.t_at AND mm.actor <> d.target
          GROUP BY d.url, d.target, mm.actor),
        mention_best AS (
          SELECT *, row_number() OVER (PARTITION BY url, target ORDER BY s_at DESC) AS rk FROM mention)
        SELECT d.url, d.target, d.t_at, d.target_row, d.target_channel,
               coalesce(r.source, m.source) AS source, coalesce(r.s_at, m.s_at) AS s_at,
               coalesce(r.source_row, m.source_row) AS source_row, coalesce(r.source_room, m.source_room) AS source_room,
               coalesce(r.prior_posters, 0) AS prior_posts, coalesce(r.named_posters, 0) AS named_posters,
               epoch(d.t_at - coalesce(r.s_at, m.s_at)) AS lag_s,
               CASE WHEN r.source IS NULL AND m.source IS NOT NULL
                         AND epoch(d.t_at - m.s_at) <= {MENTION_WINDOW_MIN} * 60 THEN 'mention'
                    WHEN r.source IS NULL THEN 'none'
                    WHEN r.named THEN 'explicit'
                    WHEN epoch(d.t_at - r.s_at) <= {WINDOW_HOURS} * 3600 THEN 'temporal'
                    ELSE 'stale' END AS evidence
        FROM trace_adopt d
        LEFT JOIN ranked r ON r.url = d.url AND r.target = d.target AND r.rk = 1
        LEFT JOIN mention_best m ON m.url = d.url AND m.target = d.target AND m.rk = 1""")

    # 6. Artifact summary with origin label.
    build(con, "trace_artifacts", f"""
        WITH goal_text AS (
          SELECT string_agg(goal, ' ') AS g FROM village_goals
          UNION ALL SELECT string_agg(coalesce(description, '') || ' ' || coalesce(name, ''), ' ') FROM agent_goals),
        t0 AS (SELECT url, min(t_at) AS t_first FROM trace_edges_scored GROUP BY url),
        ev AS (
          SELECT e.url, count(*) AS adopters,
                 count(*) FILTER (WHERE evidence = 'explicit') AS ev_explicit,
                 count(*) FILTER (WHERE evidence = 'temporal') AS ev_temporal,
                 count(*) FILTER (WHERE evidence = 'stale') AS ev_stale,
                 count(*) FILTER (WHERE evidence = 'mention') AS ev_mention,
                 count(*) FILTER (WHERE evidence = 'none') AS ev_none,
                 median(lag_s) FILTER (WHERE evidence IN ('explicit', 'temporal')) AS median_lag_s,
                 count(*) FILTER (WHERE evidence = 'none'
                                  AND e.t_at <= t0.t_first + INTERVAL {BROADCAST_MINUTES} MINUTE) AS early_unsourced
          FROM trace_edges_scored e JOIN t0 USING (url) GROUP BY e.url)
        SELECT a.*, ev.* EXCLUDE (url),
               CASE WHEN a.is_noise THEN 'noise'
                    WHEN EXISTS (SELECT 1 FROM goal_text WHERE contains(g, a.url)) THEN 'organizer'
                    WHEN a.first_actor LIKE 'human:%' THEN 'human'
                    WHEN ev.early_unsourced >= {BROADCAST_AGENTS} THEN 'broadcast_suspect'
                    WHEN a.first_channel <> 'chat' THEN 'agent_created'
                    ELSE 'agent_chat' END AS origin
        FROM trace_art a LEFT JOIN ev USING (url)""")
    log("TRACE DONE")


if __name__ == "__main__":
    sys.exit(main())
