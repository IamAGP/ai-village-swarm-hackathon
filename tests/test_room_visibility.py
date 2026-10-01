"""Room visibility cases use synthetic rows; no AI Village data is required."""

from datetime import datetime

import duckdb
import pytest

from explorer.tracer import TRACE_EDGES_SCORED_SQL, TRACE_ROOM_PRESENCE_SQL


URL = "https://example.test/room-story"


def test_presence_combines_own_chat_posts_and_enter_room_events():
    con = duckdb.connect()
    con.execute("""CREATE TABLE chat_messages (
        agent_speaker_id VARCHAR, speaker_type VARCHAR, created_at TIMESTAMP, room_id VARCHAR)""")
    con.execute("""INSERT INTO chat_messages VALUES
        ('agent', 'agent', '2026-03-01 11:00:00', 'room-a'),
        (NULL, 'user', '2026-03-01 11:01:00', 'room-b')""")
    con.execute("""CREATE TABLE events_slim (
        agent_id VARCHAR, action_type VARCHAR, created_at TIMESTAMP, room_id VARCHAR)""")
    con.execute("""INSERT INTO events_slim VALUES
        ('agent', 'ENTER_ROOM', '2026-03-01 11:02:00', 'room-b'),
        ('agent', 'WAIT', '2026-03-01 11:03:00', 'room-a')""")

    rows = con.execute(f"SELECT * FROM ({TRACE_ROOM_PRESENCE_SQL}) ORDER BY seen_at").fetchall()
    assert rows == [
        ("agent", datetime(2026, 3, 1, 11), "room-a"),
        ("agent", datetime(2026, 3, 1, 11, 2), "room-b"),
    ]


def edge(*, adoption="2026-03-01 12:10:00", posts=(), mentions=(), presence=(), target_text=" story "):
    con = duckdb.connect()
    con.execute("CREATE TABLE agents (id VARCHAR, name VARCHAR)")
    con.execute("INSERT INTO agents VALUES ('alice', 'Alice'), ('bob', 'Bob')")
    con.execute("""CREATE TABLE trace_adopt (
        url VARCHAR, target VARCHAR, t_at TIMESTAMP, target_row VARCHAR,
        target_channel VARCHAR, target_text VARCHAR)""")
    con.execute("INSERT INTO trace_adopt VALUES (?, 'target', ?, 'target-row', 'action', ?)",
                [URL, adoption, target_text])
    con.execute("""CREATE TABLE trace_uses (
        url VARCHAR, agent_id VARCHAR, human VARCHAR, created_at TIMESTAMP,
        row_id VARCHAR, room_id VARCHAR, channel VARCHAR)""")
    if posts:
        con.executemany("INSERT INTO trace_uses VALUES (?, ?, NULL, ?, ?, ?, 'chat')",
                        [(URL, source, at, row_id, room) for source, at, row_id, room in posts])
    con.execute("""CREATE TABLE trace_slug_mentions (
        url VARCHAR, actor VARCHAR, created_at TIMESTAMP, row_id VARCHAR, room_id VARCHAR)""")
    if mentions:
        con.executemany("INSERT INTO trace_slug_mentions VALUES (?, ?, ?, ?, ?)",
                        [(URL, source, at, row_id, room) for source, at, row_id, room in mentions])
    con.execute("CREATE TABLE trace_room_presence (agent_id VARCHAR, seen_at TIMESTAMP, room_id VARCHAR)")
    if presence:
        con.executemany("INSERT INTO trace_room_presence VALUES ('target', ?, ?)", presence)
    cursor = con.execute(f"SELECT * FROM ({TRACE_EDGES_SCORED_SQL})")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    assert len(rows) == 1
    return dict(zip(columns, rows[0]))


@pytest.mark.parametrize("post_kind", ["url", "mention"])
def test_same_room_source_is_visible(post_kind):
    candidate = ("alice", "2026-03-01 12:00:00", "alice-post", "room-a")
    kwargs = {"posts" if post_kind == "url" else "mentions": [candidate]}
    result = edge(presence=[("2026-03-01 11:55:00", "room-a")], **kwargs)
    assert result["source"] == "alice"
    assert result["evidence"] == ("temporal" if post_kind == "url" else "mention")
    assert result["dropped_candidates"] == 0
    assert not result["room_unknown"]


def test_cross_room_candidate_falls_back_to_earlier_visible_post():
    result = edge(
        posts=[("alice", "2026-03-01 12:00:00", "alice-post", "room-a"),
               ("bob", "2026-03-01 12:05:00", "bob-post", "room-b")],
        presence=[("2026-03-01 11:55:00", "room-a")],
    )
    assert result["source"] == "alice"
    assert result["source_row"] == "alice-post"
    assert result["evidence"] == "temporal"
    assert result["dropped_candidates"] == 1
    assert result["dropped_url_candidates"] == 1


def test_latest_post_by_same_actor_can_be_hidden_while_earlier_one_is_visible():
    result = edge(
        posts=[("alice", "2026-03-01 12:00:00", "visible-post", "room-a"),
               ("alice", "2026-03-01 12:05:00", "hidden-post", "room-b")],
        presence=[("2026-03-01 11:55:00", "room-a")],
    )
    assert result["source"] == "alice"
    assert result["source_row"] == "visible-post"
    assert result["dropped_candidates"] == 1


def test_url_post_and_its_slug_are_counted_as_one_candidate():
    post = ("bob", "2026-03-01 12:00:00", "bob-post", "room-b")
    result = edge(
        posts=[post], mentions=[post],
        presence=[("2026-03-01 11:55:00", "room-a")],
    )
    assert result["evidence"] == "cross_room"
    assert result["dropped_url_candidates"] == 1
    assert result["dropped_mention_candidates"] == 0
    assert result["dropped_candidates"] == 1


@pytest.mark.parametrize("post_kind", ["url", "mention"])
def test_only_cross_room_candidates_get_explicit_uncertainty(post_kind):
    candidate = ("bob", "2026-03-01 12:00:00", "bob-post", "room-b")
    kwargs = {"posts" if post_kind == "url" else "mentions": [candidate]}
    result = edge(presence=[("2026-03-01 11:55:00", "room-a")], **kwargs)
    assert result["source"] is None
    assert result["evidence"] == "cross_room"
    assert result["dropped_candidates"] == 1
    assert not result["room_unknown"]


@pytest.mark.parametrize("post_kind", ["url", "mention"])
def test_entering_room_after_post_but_before_adoption_restores_visibility(post_kind):
    candidate = ("bob", "2026-03-01 12:00:00", "bob-post", "room-b")
    kwargs = {"posts" if post_kind == "url" else "mentions": [candidate]}
    result = edge(
        presence=[("2026-03-01 11:55:00", "room-a"),
                  ("2026-03-01 12:05:00", "room-b")], **kwargs)
    assert result["source"] == "bob"
    assert result["evidence"] == ("temporal" if post_kind == "url" else "mention")
    assert result["dropped_candidates"] == 0


def test_before_rooms_started_post_is_visible_regardless_of_room():
    result = edge(
        adoption="2026-02-24 12:10:00",
        posts=[("bob", "2026-02-24 12:00:00", "bob-post", "room-b")],
        presence=[("2026-02-24 11:55:00", "room-a")],
    )
    assert result["source"] == "bob"
    assert result["evidence"] == "temporal"
    assert result["dropped_candidates"] == 0
    assert not result["room_unknown"]


def test_missing_presence_keeps_candidate_and_marks_uncertainty():
    result = edge(posts=[("bob", "2026-03-01 12:00:00", "bob-post", "room-b")])
    assert result["source"] == "bob"
    assert result["evidence"] == "temporal"
    assert result["dropped_candidates"] == 0
    assert result["room_unknown"]
