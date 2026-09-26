"""Regression coverage for text and source matching on model-output adoptions."""

import duckdb

from explorer.tracer import TRACE_ADOPT_SQL, TRACE_EDGES_SCORED_SQL


def test_talk_only_adoption_names_prior_poster():
    con = duckdb.connect()
    con.execute("CREATE TABLE agents (id VARCHAR, name VARCHAR)")
    con.execute("INSERT INTO agents VALUES ('poster', 'Alice')")
    con.execute("CREATE TABLE trace_art (url VARCHAR, is_noise BOOLEAN)")
    con.execute("INSERT INTO trace_art VALUES ('https://example.test/story', false)")
    con.execute("""CREATE TABLE trace_first_use (
        url VARCHAR, actor VARCHAR, first_at TIMESTAMP, row_id VARCHAR,
        channel VARCHAR, is_human BOOLEAN)""")
    con.execute("""INSERT INTO trace_first_use VALUES
        ('https://example.test/story', 'talker', '2026-09-26 12:01:00', 'talk', 'model_output', false),
        ('https://example.test/story', 'actor', '2026-09-26 12:02:00', 'action', 'model_output', false)""")
    con.execute("CREATE TABLE chat_messages (id VARCHAR, content VARCHAR)")
    con.execute("CREATE TABLE computer_use_turns (id VARCHAR, agent_action JSON, agent_messages JSON)")
    con.execute("""INSERT INTO computer_use_turns VALUES
        ('talk', NULL, '["Alice shared https://example.test/story"]'),
        ('action', '{"command":"open"}', '["Alice shared https://example.test/story"]')""")
    con.execute("""CREATE TABLE trace_uses (
        url VARCHAR, agent_id VARCHAR, human VARCHAR, created_at TIMESTAMP,
        row_id VARCHAR, room_id VARCHAR, channel VARCHAR)""")
    con.execute("""INSERT INTO trace_uses VALUES
        ('https://example.test/story', 'poster', NULL, '2026-09-26 12:00:00', 'post', 'room', 'chat')""")
    con.execute("""CREATE TABLE trace_slug_mentions (
        url VARCHAR, actor VARCHAR, created_at TIMESTAMP, row_id VARCHAR, room_id VARCHAR)""")
    con.execute("CREATE TABLE trace_room_presence (agent_id VARCHAR, seen_at TIMESTAMP, room_id VARCHAR)")

    con.execute(f"CREATE VIEW trace_adopt AS {TRACE_ADOPT_SQL}")
    texts = dict(con.execute("SELECT target, target_text FROM trace_adopt").fetchall())
    assert " alice shared https example.test story " in texts["talker"]
    assert " alice shared https example.test story " in texts["actor"]

    con.execute(f"CREATE VIEW trace_edges_scored AS {TRACE_EDGES_SCORED_SQL}")
    edges = dict(con.execute("SELECT target, evidence FROM trace_edges_scored").fetchall())
    assert edges == {"talker": "explicit", "actor": "explicit"}
