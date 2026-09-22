"""Convert the AI Village JSONL tables to typed Parquet + derived "slim" tables for the explorer.

Runs on the explorer box. Idempotent: a table whose Parquet file already exists is skipped,
so a killed run resumes where it stopped. One timestamped log line per table.
Column types follow the dataset's SCHEMA.md (timestamps are naive UTC strings).
"""
import os
import sys
import time

import duckdb

RAW, PQ, DB = "/data/raw", "/data/parquet", "/data/explorer.duckdb"
MAX_OBJ = 256 * 1024 * 1024  # some events carry very large raw model outputs

V, J, B, I = "VARCHAR", "JSON", "BOOLEAN", "BIGINT"
TS = ("created_at", "updated_at")
# Explicit schemas for the large, heterogeneous tables (provider-shaped JSON must stay JSON).
SCHEMAS = {
    "events": {"id": V, "event_index": I, "data": J, "village_id": V, "created_at": V, "updated_at": V},
    "chat_messages": {"id": V, "agent_speaker_id": V, "user_speaker_id": V, "speaker_type": V,
                      "content": V, "room_id": V, "created_at": V, "updated_at": V, "has_been_approved": B},
    "computer_use_sessions": {"id": V, "agent_id": V, "village_id": V, "created_at": V, "updated_at": V,
                              "has_been_asked_to_stop": B, "session_goal": V, "short_displayed_session_goal": V},
    "computer_use_turns": {"id": V, "session_id": V, "agent_action": J, "agent_messages": J, "output": J,
                           "error": J, "system": J, "screenshot_is_redacted": B,
                           "has_redaction_been_overruled": B, "created_at": V, "updated_at": V},
    "agent_memories": {"id": V, "content": V, "agent_id": V, "created_at": V, "updated_at": V},
    "summaries": {"id": V, "village_id": V, "type": V, "summary_target": V, "content": V,
                  "generated_by": V, "created_at": V, "updated_at": V, "summary_date": V},
    "claude_code_messages": {"id": V, "agent_id": V, "sdk_session_id": V, "message_type": V,
                             "message_subtype": V, "content": J, "created_at": V},
}
SMALL = ["agents", "villages", "village_goals", "agent_goals", "chat_rooms", "claude_code_sessions"]

# Derived tables: cheap-to-scan columns plus the joins the explorer needs on every page.
DERIVED = {
    "turns_slim": """
        SELECT t.id, t.session_id, s.agent_id, t.created_at,
               (timezone('America/Los_Angeles', t.created_at::TIMESTAMPTZ))::DATE AS pt_day,
               CASE WHEN t.agent_action IS NULL                            THEN NULL
                    WHEN t.agent_action->>'action' IS NOT NULL             THEN t.agent_action->>'action'
                    WHEN json_exists(t.agent_action, '$.command')
                      OR json_exists(t.agent_action, '$.restart')          THEN 'bash'
                    ELSE 'other' END                               AS action,
               t.agent_action                                     AS agent_action,
               -- Discriminating keys per provider (SCHEMA.md: shapes vary by provider, match on shape).
               CASE WHEN t.agent_messages IS NULL                                 THEN 'null'
                    WHEN json_type(t.agent_messages) = 'ARRAY'                    THEN 'openai_responses'
                    WHEN json_exists(t.agent_messages, '$.candidates')            THEN 'gemini'
                    WHEN json_exists(t.agent_messages, '$.stop_reason')           THEN 'anthropic'
                    WHEN json_exists(t.agent_messages, '$.choices')               THEN 'openai_chat_completion'
                    WHEN json_exists(t.agent_messages, '$.tool_calls')
                      OR json_exists(t.agent_messages, '$.reasoning_content')     THEN 'openai_chat_message'
                    ELSE 'other' END                               AS msg_shape,
               length(t.agent_messages::VARCHAR)                  AS msg_len,
               t.output IS NOT NULL                               AS has_output,
               t.error  IS NOT NULL                               AS has_error,
               t.screenshot_is_redacted, t.has_redaction_been_overruled
        FROM computer_use_turns t LEFT JOIN computer_use_sessions s ON s.id = t.session_id""",
    "events_slim": """
        SELECT id, event_index, created_at,
               (timezone('America/Los_Angeles', created_at::TIMESTAMPTZ))::DATE AS pt_day,
               data->>'actionType'                                             AS action_type,
               data->>'speakerType'                                            AS speaker_type,
               -- speakerId is a user id on USER_TALK; keep agents and users apart.
               CASE WHEN coalesce(data->>'speakerType', 'agent') = 'agent'
                    THEN coalesce(data->>'agentId', data->>'speakerId') END    AS agent_id,
               CASE WHEN data->>'speakerType' = 'user' THEN data->>'speakerId' END AS user_id,
               data->>'speakerName'                                            AS speaker_name,
               data->>'roomId'                                                 AS room_id,
               data->>'messageId'                                              AS message_id,
               data->>'computerUseSessionId'                                   AS session_id,
               TRY_CAST(data->>'cost' AS DOUBLE)                               AS cost,
               TRY_CAST(data->>'inputTokens' AS BIGINT)                        AS input_tokens,
               TRY_CAST(data->>'outputTokens' AS BIGINT)                       AS output_tokens,
               coalesce(data->>'content', data->>'sessionGoal', data->>'summary',
                        data->>'nextSessionGoal', data->>'query')              AS text,
               length(data::VARCHAR)                                           AS data_len
        FROM events""",
    "memories_slim": """
        SELECT id, agent_id, created_at,
               (timezone('America/Los_Angeles', created_at::TIMESTAMPTZ))::DATE AS pt_day,
               length(content) AS content_len
        FROM agent_memories""",
}


def log(msg):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), msg, flush=True)


def ts_replace(con, source):
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()]
    rep = [f"TRY_CAST({c} AS TIMESTAMP) AS {c}" for c in TS if c in cols]
    return f"SELECT * REPLACE ({', '.join(rep)}) FROM {source}" if rep else f"SELECT * FROM {source}"


def view(con, name):
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{PQ}/{name}.parquet')")


def main():
    os.makedirs(PQ, exist_ok=True)
    con = duckdb.connect(DB)
    con.execute("SET memory_limit='20GB'; SET temp_directory='/data/tmp'; SET threads=4;"
                "SET preserve_insertion_order=false; SET TimeZone='UTC';")
    con.execute("INSTALL icu; LOAD icu;")

    for name in SMALL + list(SCHEMAS):
        out = f"{PQ}/{name}.parquet"
        if not os.path.exists(out):
            t0 = time.time()
            src = f"'{RAW}/{name}.jsonl.gz'"
            if name in SCHEMAS:
                cols = "{" + ", ".join(f"'{k}': '{v}'" for k, v in SCHEMAS[name].items()) + "}"
                source = (f"read_json({src}, format='newline_delimited', columns={cols}, "
                          f"maximum_object_size={MAX_OBJ})")
            else:
                source = f"read_json_auto({src}, format='newline_delimited', maximum_object_size={MAX_OBJ})"
            try:
                con.execute(f"COPY ({ts_replace(con, source)}) TO '{out}.tmp' (FORMAT parquet, COMPRESSION zstd)")
                os.replace(f"{out}.tmp", out)
                rows = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
                log(f"TABLE {name} rows={rows} bytes={os.path.getsize(out)} secs={time.time() - t0:.0f}")
            except Exception as e:  # keep going; the profile reports what is missing
                log(f"ERROR {name}: {str(e)[:400]}")
                continue
        else:
            log(f"SKIP {name} (exists)")
        view(con, name)

    for name, sql in DERIVED.items():
        out = f"{PQ}/{name}.parquet"
        if not os.path.exists(out):
            t0 = time.time()
            try:
                con.execute(f"COPY ({sql}) TO '{out}.tmp' (FORMAT parquet, COMPRESSION zstd)")
                os.replace(f"{out}.tmp", out)
                rows = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
                log(f"DERIVED {name} rows={rows} bytes={os.path.getsize(out)} secs={time.time() - t0:.0f}")
            except Exception as e:
                log(f"ERROR {name}: {str(e)[:400]}")
                continue
        view(con, name)
    log("BUILD DONE")


if __name__ == "__main__":
    sys.exit(main())
