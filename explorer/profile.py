"""Profile the AI Village Parquet tables: shape, coverage, JSON structures, joins, activity.

Runs on the explorer box after build.py. Writes one JSON per section to /data/profile
(aggregates only — counts, lengths, key signatures, low-cardinality top values; never raw text)
and skips sections whose output already exists. One timestamped log line per section.
"""
import json
import os
import sys
import time

import duckdb

DB, PROF, RAW = "/data/explorer.duckdb", "/data/profile", "/data/raw"
TABLES = ["agents", "villages", "village_goals", "agent_goals", "chat_rooms", "claude_code_sessions",
          "events", "chat_messages", "computer_use_sessions", "computer_use_turns", "agent_memories",
          "summaries", "claude_code_messages", "turns_slim", "events_slim", "memories_slim"]
TEXT_TYPES = ("VARCHAR", "JSON")
TOP_MAX_DISTINCT = 40
# Free-text columns: report lengths only, never values.
NO_VALUES = {"content", "session_goal", "short_displayed_session_goal", "goal", "description", "text",
             "status_message", "village_goal", "summary_target", "name", "short_name"}


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def rows(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def section(name, fn, con):
    out = f"{PROF}/{name}.json"
    if os.path.exists(out):
        log(f"SKIP {name}")
        return
    t0 = time.time()
    try:
        result = fn(con)
    except Exception as e:
        log(f"ERROR {name}: {str(e)[:400]}")
        return
    with open(out + ".tmp", "w") as f:
        json.dump(result, f, indent=1, default=str)
    os.replace(out + ".tmp", out)
    log(f"SECTION {name} secs={time.time() - t0:.0f}")


def table_profile(table):
    def fn(con):
        cols = rows(con, f"DESCRIBE {table}")
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        prof = {"table": table, "rows": n, "columns": {}}
        names = [c["column_name"] for c in cols]
        if "created_at" in names:
            prof["created_min"], prof["created_max"] = con.execute(
                f"SELECT min(created_at), max(created_at) FROM {table}").fetchone()
        for c in cols:
            col, typ = c["column_name"], c["column_type"]
            q = f'"{col}"'
            info = {"type": typ}
            info["nulls"] = con.execute(f"SELECT count(*) - count({q}) FROM {table}").fetchone()[0]
            if typ in TEXT_TYPES:
                info["len_avg"], info["len_p50"], info["len_p99"], info["len_max"] = con.execute(
                    f"SELECT avg(length({q}::VARCHAR)), quantile_cont(length({q}::VARCHAR), 0.5), "
                    f"quantile_cont(length({q}::VARCHAR), 0.99), max(length({q}::VARCHAR)) FROM {table}").fetchone()
            if typ != "JSON":
                info["approx_distinct"] = con.execute(f"SELECT approx_count_distinct({q}) FROM {table}").fetchone()[0]
                if info["approx_distinct"] <= TOP_MAX_DISTINCT and col not in NO_VALUES:
                    info["top"] = rows(con, f"SELECT {q} AS value, count(*) AS n FROM {table} "
                                            f"GROUP BY 1 ORDER BY 2 DESC LIMIT {TOP_MAX_DISTINCT}")
            prof["columns"][col] = info
        return prof
    return fn


def json_shapes(con):
    """Top-level key signatures of every JSON column, split by the discriminator the schema documents."""
    sig = "array_to_string(list_sort(json_keys({c})), ',')"
    return {
        "events.data_by_action_type": rows(con, f"""
            SELECT data->>'actionType' AS action_type, {sig.format(c='data')} AS keys, count(*) AS n
            FROM events GROUP BY ALL ORDER BY action_type, n DESC"""),
        "turns.agent_action.action": rows(con, """
            SELECT action, count(*) AS n FROM turns_slim GROUP BY 1 ORDER BY 2 DESC"""),
        "turns.agent_action_keys_by_action": rows(con, f"""
            SELECT agent_action->>'action' AS action, {sig.format(c='agent_action')} AS keys, count(*) AS n
            FROM computer_use_turns WHERE agent_action IS NOT NULL GROUP BY ALL ORDER BY n DESC LIMIT 80"""),
        "turns.msg_shape_by_model": rows(con, """
            SELECT a.model_string, t.msg_shape, count(*) AS n, round(avg(t.msg_len)) AS avg_len
            FROM turns_slim t LEFT JOIN agents a ON a.id = t.agent_id GROUP BY ALL ORDER BY 1, 3 DESC"""),
        "turns.agent_messages_keys": rows(con, f"""
            SELECT json_type(agent_messages) AS json_type,
                   CASE WHEN json_type(agent_messages) = 'OBJECT' THEN {sig.format(c='agent_messages')} END AS keys,
                   count(*) AS n
            FROM computer_use_turns GROUP BY ALL ORDER BY n DESC LIMIT 40"""),
        "turns.output_error_system_types": rows(con, """
            SELECT json_type(output) AS output_t, json_type(error) AS error_t, json_type(system) AS system_t,
                   count(*) AS n FROM computer_use_turns GROUP BY ALL ORDER BY n DESC"""),
        "claude_code_messages.content_keys": rows(con, f"""
            SELECT message_type, message_subtype, {sig.format(c='content')} AS keys, count(*) AS n
            FROM claude_code_messages GROUP BY ALL ORDER BY n DESC LIMIT 40"""),
    }


def relations(con):
    """Foreign-key coverage: how many child rows resolve to a parent."""
    checks = {
        "turns.session_id -> sessions.id": ("computer_use_turns", "session_id", "computer_use_sessions", "id"),
        "sessions.agent_id -> agents.id": ("computer_use_sessions", "agent_id", "agents", "id"),
        "chat.agent_speaker_id -> agents.id": ("chat_messages", "agent_speaker_id", "agents", "id"),
        "chat.room_id -> chat_rooms.id": ("chat_messages", "room_id", "chat_rooms", "id"),
        "memories.agent_id -> agents.id": ("agent_memories", "agent_id", "agents", "id"),
        "events.agent_id -> agents.id": ("events_slim", "agent_id", "agents", "id"),
        "events.message_id -> chat.id": ("events_slim", "message_id", "chat_messages", "id"),
        "events.session_id -> sessions.id": ("events_slim", "session_id", "computer_use_sessions", "id"),
        "agent_goals.agent_id -> agents.id": ("agent_goals", "agent_id", "agents", "id"),
        "cc_messages.agent_id -> agents.id": ("claude_code_messages", "agent_id", "agents", "id"),
    }
    out = {}
    for label, (c, ck, p, pk) in checks.items():
        out[label] = rows(con, f"""
            SELECT count(*) FILTER (WHERE c.{ck} IS NOT NULL) AS non_null,
                   count(*) FILTER (WHERE c.{ck} IS NOT NULL AND p.{pk} IS NULL) AS dangling
            FROM {c} c LEFT JOIN {p} p ON p.{pk} = c.{ck}""")[0]
    out["sessions_without_turns"] = con.execute("""
        SELECT count(*) FROM computer_use_sessions s
        WHERE NOT EXISTS (SELECT 1 FROM computer_use_turns t WHERE t.session_id = s.id)""").fetchone()[0]
    return out


def activity(con):
    """Per-agent lifetime and volume, and per-month volume per table."""
    return {
        "per_agent": rows(con, """
            WITH ch AS (SELECT agent_speaker_id AS agent_id, count(*) AS n, min(created_at) AS f, max(created_at) AS l
                        FROM chat_messages WHERE agent_speaker_id IS NOT NULL GROUP BY 1),
                 se AS (SELECT agent_id, count(*) AS n FROM computer_use_sessions GROUP BY 1),
                 tu AS (SELECT agent_id, count(*) AS n, min(created_at) AS f, max(created_at) AS l FROM turns_slim GROUP BY 1),
                 me AS (SELECT agent_id, count(*) AS n, round(avg(content_len)) AS avg_len FROM memories_slim GROUP BY 1),
                 ev AS (SELECT agent_id, count(*) AS n, round(sum(cost), 2) AS cost FROM events_slim GROUP BY 1)
            SELECT a.name, a.model_string, a.is_participating, a.created_at AS joined,
                   least(ch.f, tu.f) AS first_active, greatest(ch.l, tu.l) AS last_active,
                   ch.n AS chat_msgs, se.n AS sessions, tu.n AS turns, me.n AS memories, me.avg_len AS mem_avg_len,
                   ev.n AS events, ev.cost AS event_cost
            FROM agents a LEFT JOIN ch ON ch.agent_id = a.id LEFT JOIN se ON se.agent_id = a.id
            LEFT JOIN tu ON tu.agent_id = a.id LEFT JOIN me ON me.agent_id = a.id LEFT JOIN ev ON ev.agent_id = a.id
            ORDER BY a.created_at"""),
        "per_month": rows(con, """
            SELECT m, sum(chat) AS chat, sum(turns) AS turns, sum(sessions) AS sessions, sum(memories) AS memories, sum(events) AS events
            FROM (
              SELECT date_trunc('month', created_at) AS m, count(*) AS chat, 0 AS turns, 0 AS sessions, 0 AS memories, 0 AS events FROM chat_messages GROUP BY 1
              UNION ALL SELECT date_trunc('month', created_at), 0, count(*), 0, 0, 0 FROM turns_slim GROUP BY 1
              UNION ALL SELECT date_trunc('month', created_at), 0, 0, count(*), 0, 0 FROM computer_use_sessions GROUP BY 1
              UNION ALL SELECT date_trunc('month', created_at), 0, 0, 0, count(*), 0 FROM memories_slim GROUP BY 1
              UNION ALL SELECT date_trunc('month', created_at), 0, 0, 0, 0, count(*) FROM events_slim GROUP BY 1)
            GROUP BY 1 ORDER BY 1"""),
        "event_types_per_month": rows(con, """
            SELECT date_trunc('month', created_at) AS m, action_type, count(*) AS n FROM events_slim GROUP BY ALL ORDER BY 1, 3 DESC"""),
        "rooms": rows(con, """
            SELECT r.name, count(c.id) AS msgs, min(c.created_at) AS first, max(c.created_at) AS last
            FROM chat_rooms r LEFT JOIN chat_messages c ON c.room_id = r.id GROUP BY 1 ORDER BY 2 DESC"""),
        "speaker_types": rows(con, "SELECT speaker_type, count(*) AS n FROM chat_messages GROUP BY 1"),
        "summaries_by_type": rows(con, "SELECT type, generated_by, count(*) AS n FROM summaries GROUP BY ALL ORDER BY 3 DESC"),
    }


def screenshots(con):
    """Cross-check turns per PT day against the image index shipped with the dataset."""
    idx = json.load(open(f"{RAW}/images_index.json"))
    con.execute("CREATE OR REPLACE TEMP TABLE img_idx (day DATE, turns BIGINT, images BIGINT)")
    con.executemany("INSERT INTO img_idx VALUES (?, ?, ?)",
                    [(d, v.get("turns"), v.get("images")) for d, v in idx.items()])
    return {
        "index_days": len(idx),
        "index_images_total": sum(v.get("images") or 0 for v in idx.values()),
        "index_turns_total": sum(v.get("turns") or 0 for v in idx.values()),
        "redacted_turns": con.execute("SELECT count(*) FILTER (WHERE screenshot_is_redacted), "
                                      "count(*) FILTER (WHERE has_redaction_been_overruled) FROM turns_slim").fetchone(),
        "day_mismatches": rows(con, """
            SELECT coalesce(t.pt_day, i.day) AS day, t.n AS turns_in_table, i.turns AS turns_in_index, i.images
            FROM (SELECT pt_day, count(*) n FROM turns_slim GROUP BY 1) t
            FULL JOIN img_idx i ON i.day = t.pt_day
            WHERE t.n IS DISTINCT FROM i.turns ORDER BY 1 LIMIT 60"""),
    }


def main():
    os.makedirs(PROF, exist_ok=True)
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET memory_limit='20GB'; SET temp_directory='/data/tmp'; SET threads=4; SET TimeZone='UTC';")
    con.execute("LOAD icu;")
    for t in TABLES:
        section(f"table_{t}", table_profile(t), con)
    section("json_shapes", json_shapes, con)
    section("relations", relations, con)
    section("activity", activity, con)
    section("screenshots", screenshots, con)
    log("PROFILE DONE")


if __name__ == "__main__":
    sys.exit(main())
