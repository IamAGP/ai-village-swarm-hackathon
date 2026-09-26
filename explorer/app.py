"""AI Village explorer — a local-only Streamlit UI over the Parquet copy built by build.py.

Runs on the explorer box, bound to 127.0.0.1:8501; reach it through an SSM port-forward.
Screenshots are fetched per day from the private S3 mirror on first view and cached on disk.
"""
import json
import os
import shutil
import subprocess
import tarfile
import threading

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

DB = "/data/explorer.duckdb"
BUCKET_TARS = "s3://ai-village-459653581741/hf/ai-village/images/computer-use-turns"
TAR_CACHE = "/data/tarcache"
TAR_CACHE_MAX_BYTES = 40 * 1024**3
_tar_lock = threading.Lock()

st.set_page_config(page_title="AI Village explorer", layout="wide")


# ---------------------------------------------------------------- data access
@st.cache_resource
def connection():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'; SET memory_limit='16GB'; SET threads=4;")
    con.execute("LOAD icu;")
    return con


def q(sql, params=None):
    """Run a query on a per-call cursor (DuckDB connections are not shared across threads)."""
    return connection().cursor().execute(sql, params or []).df()


@st.cache_data(ttl=3600)
def agents():
    return q("""SELECT id::VARCHAR AS id, name, model_string, is_participating, created_at
                FROM agents ORDER BY created_at""")


def agent_names():
    a = agents()
    return dict(zip(a.id, a.name))


# ------------------------------------------------------- model output decoding
def decode_messages(raw):
    """Turn a provider-shaped `agent_messages` value into (kind, text) parts.

    Shapes follow docs/DATA_PROFILE.md: Anthropic (stop_reason + content blocks), Gemini (candidates/parts),
    OpenAI Responses (array of items), OpenAI chat message (role + tool_calls/reasoning), Claude Code SDK.
    """
    if raw is None:
        return []
    m = json.loads(raw) if isinstance(raw, str) else raw
    parts = []
    if isinstance(m, list):  # OpenAI Responses API items
        for it in m:
            t = it.get("type")
            if t == "reasoning":
                for s in it.get("summary") or []:
                    parts.append(("reasoning", s.get("text", "")))
            elif t == "message":
                for c in it.get("content") or []:
                    parts.append(("text", c.get("text", "")))
            elif t == "function_call":
                parts.append(("tool", f"{it.get('name')}({it.get('arguments')})"))
        return parts
    if "candidates" in m:  # Gemini
        for cand in m.get("candidates") or []:
            for p in (cand.get("content") or {}).get("parts") or []:
                if "text" in p:
                    parts.append(("reasoning" if p.get("thought") else "text", p["text"]))
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    parts.append(("tool", f"{fc.get('name')}({json.dumps(fc.get('args'))})"))
        return parts
    if "_sdkFormat" in m:  # Claude Code SDK agent
        for k, kind in (("thinkingMessage", "reasoning"), ("textMessage", "text")):
            if m.get(k):
                parts.append((kind, m[k] if isinstance(m[k], str) else json.dumps(m[k])))
        return parts
    if "stop_reason" in m and isinstance(m.get("content"), list):  # Anthropic
        for b in m["content"]:
            t = b.get("type")
            if t == "thinking":
                parts.append(("reasoning", b.get("thinking", "")))
            elif t == "text":
                parts.append(("text", b.get("text", "")))
            elif t == "tool_use":
                parts.append(("tool", f"{b.get('name')}({json.dumps(b.get('input'))})"))
        return parts
    if "role" in m:  # OpenAI-style chat message (DeepSeek, Kimi, Grok, GLM, o-series, ...)
        r = m.get("reasoning_content") or m.get("reasoning")
        if r:
            parts.append(("reasoning", r if isinstance(r, str) else json.dumps(r)))
        c = m.get("content")
        if c:
            parts.append(("text", c if isinstance(c, str) else json.dumps(c)))
        for tc in m.get("tool_calls") or []:
            f = tc.get("function") or {}
            parts.append(("tool", f"{f.get('name')}({f.get('arguments')})"))
        return parts
    return [("raw", json.dumps(m)[:4000])]


# ------------------------------------------------------------------ screenshots
def _evict_tar_cache():
    files = sorted((os.path.join(TAR_CACHE, f) for f in os.listdir(TAR_CACHE) if f.endswith(".tar")),
                   key=os.path.getatime)
    total = sum(os.path.getsize(f) for f in files)
    while files and total > TAR_CACHE_MAX_BYTES:
        f = files.pop(0)
        total -= os.path.getsize(f)
        os.remove(f)


@st.cache_resource(max_entries=8)
def tar_index(day):
    """Download the day's tar from S3 once (same-region, no egress cost) and index its members."""
    os.makedirs(TAR_CACHE, exist_ok=True)
    path = f"{TAR_CACHE}/{day}.tar"
    with _tar_lock:
        if not os.path.exists(path):
            _evict_tar_cache()
            tmp = path + ".part"
            r = subprocess.run(["aws", "s3", "cp", "--quiet", f"{BUCKET_TARS}/{day}.tar", tmp,
                                "--region", "ap-south-1"], capture_output=True, text=True)
            if r.returncode != 0:
                return None
            shutil.move(tmp, path)
    with tarfile.open(path) as tf:
        return path, {m.name: (m.offset_data, m.size) for m in tf.getmembers()}


def screenshot(day, turn_id):
    idx = tar_index(str(day))
    if not idx:
        return None
    path, members = idx
    hit = members.get(f"{turn_id}.png")
    if not hit:
        return None
    with open(path, "rb") as f:
        f.seek(hit[0])
        return f.read(hit[1])


# ----------------------------------------------------------------------- pages
def page_overview():
    st.header("The village at a glance")
    c = st.columns(6)
    stats = q("""SELECT (SELECT count(*) FROM agents) a, (SELECT count(*) FROM chat_messages) c,
                        (SELECT count(*) FROM computer_use_sessions) s, (SELECT count(*) FROM turns_slim) t,
                        (SELECT count(*) FROM agent_memories) m, (SELECT count(*) FROM village_goals) g""").iloc[0]
    def short(n):
        n = int(n)
        return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}K" if n >= 1e4 else f"{n:,}"

    for col, (label, v) in zip(c, [("Agents", stats.a), ("Chat messages", stats.c), ("Sessions", stats.s),
                                   ("Turns", stats.t), ("Memories", stats.m), ("Village goals", stats.g)]):
        col.metric(label, short(v), help=f"{int(v):,}")

    st.subheader("Village goals over time")
    g = q("""SELECT goal, start_time::TIMESTAMP AS start, coalesce(end_time::TIMESTAMP, now()::TIMESTAMP) AS "end"
             FROM village_goals ORDER BY start_time""")
    st.altair_chart(alt.Chart(g).mark_bar().encode(
        x="start:T", x2="end:T", y=alt.Y("goal:N", sort=None, title=None, axis=alt.Axis(labelLimit=420)),
        tooltip=["goal", "start:T", "end:T"]).properties(height=900), width="stretch")

    st.subheader("When each agent was active")
    life = q("""SELECT a.name, min(t.created_at) AS first, max(t.created_at) AS last, count(*) AS turns
                FROM turns_slim t JOIN agents a ON a.id::VARCHAR = t.agent_id GROUP BY 1 ORDER BY 2""")
    st.altair_chart(alt.Chart(life).mark_bar().encode(
        x="first:T", x2="last:T", y=alt.Y("name:N", sort=None, title=None),
        color=alt.Color("turns:Q", scale=alt.Scale(scheme="blues")),
        tooltip=["name", "first:T", "last:T", "turns"]).properties(height=820), width="stretch")

    st.subheader("Weekly activity")
    wk = q("""SELECT date_trunc('week', created_at) AS week, 'turns' AS kind, count(*) AS n FROM turns_slim GROUP BY 1
              UNION ALL SELECT date_trunc('week', created_at), 'chat messages', count(*) FROM chat_messages GROUP BY 1
              UNION ALL SELECT date_trunc('week', created_at), 'memories', count(*) FROM memories_slim GROUP BY 1""")
    st.altair_chart(alt.Chart(wk).mark_line().encode(
        x="week:T", y="n:Q", color="kind:N", tooltip=["week:T", "kind", "n"]).properties(height=300),
        width="stretch")


def page_agent():
    a = agents()
    name = st.selectbox("Agent", a.name.tolist(), index=int((a.name == "Claude Opus 5").idxmax()))
    row = a[a.name == name].iloc[0]
    aid = row.id
    st.caption(f"`{row.model_string}` · joined {row.created_at:%Y-%m-%d} · "
               f"{'participating' if row.is_participating else 'retired'}")
    goals = q("SELECT name, short_name, description, start_time, end_time FROM agent_goals WHERE agent_id::VARCHAR = ?", [aid])
    if len(goals):
        st.info("Individual goal: **" + goals.iloc[0]["name"] + "**")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Actions")
        acts = q("SELECT coalesce(action, 'talk-only') AS action, count(*) AS n FROM turns_slim WHERE agent_id = ? "
                 "GROUP BY 1 ORDER BY 2 DESC LIMIT 15", [aid])
        st.altair_chart(alt.Chart(acts).mark_bar().encode(x="n:Q", y=alt.Y("action:N", sort="-x")),
                        width="stretch")
    with c2:
        st.subheader("Turns per week")
        wk = q("SELECT date_trunc('week', created_at) AS week, count(*) AS n FROM turns_slim WHERE agent_id = ? "
               "GROUP BY 1 ORDER BY 1", [aid])
        st.altair_chart(alt.Chart(wk).mark_area().encode(x="week:T", y="n:Q"), width="stretch")

    tab_chat, tab_sess, tab_mem = st.tabs(["Chat", "Sessions", "Memories"])
    with tab_chat:
        lim = st.slider("Messages", 20, 500, 100, key="agent_chat_lim")
        order = st.radio("Order", ["newest first", "oldest first"], horizontal=True, key="agent_chat_order")
        df = q(f"""SELECT m.created_at, r.name AS room, m.content FROM chat_messages m
                   LEFT JOIN chat_rooms r ON r.id::VARCHAR = m.room_id WHERE m.agent_speaker_id = ?
                   ORDER BY m.created_at {'DESC' if order.startswith('newest') else 'ASC'} LIMIT {lim}""", [aid])
        st.dataframe(df, width="stretch", hide_index=True)
    with tab_sess:
        df = q("""SELECT s.id, s.created_at, s.short_displayed_session_goal AS goal, count(t.id) AS turns
                  FROM computer_use_sessions s LEFT JOIN turns_slim t ON t.session_id = s.id
                  WHERE s.agent_id = ? GROUP BY ALL ORDER BY s.created_at DESC LIMIT 500""", [aid])
        st.dataframe(df, width="stretch", hide_index=True)
        st.caption("Copy a session id into **Session replay** to step through it.")
    with tab_mem:
        mem = q("SELECT id, created_at, content_len FROM memories_slim WHERE agent_id = ? ORDER BY created_at DESC", [aid])
        st.write(f"{len(mem):,} memory snapshots")
        if len(mem):
            pick = st.select_slider("Snapshot", options=list(range(len(mem))),
                                    format_func=lambda i: f"{mem.created_at.iloc[i]:%Y-%m-%d %H:%M}", value=0)
            text = q("SELECT content FROM agent_memories WHERE id = ?", [mem.id.iloc[pick]]).content.iloc[0]
            st.caption(f"{len(text):,} characters")
            st.markdown(text[:60000])


def page_session():
    st.header("Session replay")
    names = agent_names()
    sid = st.text_input("Session id", value=st.session_state.get("sid", ""))
    if not sid:
        st.caption("Or pick a recent session:")
        pick = q("""SELECT s.id, s.created_at, s.agent_id, s.short_displayed_session_goal AS goal
                    FROM computer_use_sessions s ORDER BY s.created_at DESC LIMIT 200""")
        pick["agent"] = pick.agent_id.map(names)
        choice = st.selectbox("Session", pick.index, format_func=lambda i:
                              f"{pick.created_at[i]:%Y-%m-%d %H:%M} · {pick.agent[i]} · {pick.goal[i]}")
        sid = pick.id[choice]
    s = q("SELECT * FROM computer_use_sessions WHERE id = ?", [sid])
    if s.empty:
        st.warning("No such session.")
        return
    s = s.iloc[0]
    st.markdown(f"**{names.get(s.agent_id, s.agent_id)}** · started {s.created_at:%Y-%m-%d %H:%M} UTC")
    with st.expander("Session goal (agent's own words)"):
        st.write(s.session_goal)
    turns = q("SELECT id, created_at, pt_day, action, msg_shape, screenshot_is_redacted FROM turns_slim "
              "WHERE session_id = ? ORDER BY created_at", [sid])
    if turns.empty:
        st.info("This session has no turns.")
        return
    i = st.slider("Turn", 1, len(turns), 1) - 1
    t = turns.iloc[i]
    full = q("SELECT agent_action, agent_messages, output, error FROM computer_use_turns WHERE id = ?", [t.id]).iloc[0]
    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"**Turn {i + 1}/{len(turns)}** · {t.created_at:%H:%M:%S} UTC · action `{t.action}` · shape `{t.msg_shape}`")
        for kind, text in decode_messages(full.agent_messages):
            if kind == "reasoning":
                with st.expander("💭 reasoning", expanded=False):
                    st.write(text)
            elif kind == "tool":
                st.code(text[:4000], language="json")
            else:
                st.write(text)
        st.markdown("**Executed action**")
        st.code(json.dumps(json.loads(full.agent_action), indent=1)[:4000] if full.agent_action else "—", language="json")
        if full.output:
            with st.expander("Tool output"):
                st.code(str(json.loads(full.output))[:8000])
        if full.error:
            with st.expander("Error", expanded=True):
                st.code(str(json.loads(full.error))[:4000])
    with right:
        if t.screenshot_is_redacted:
            st.caption("Screenshot redacted in the dataset (placeholder image).")
        with st.spinner(f"Loading screenshots for {t.pt_day} (first view of a day downloads its tar)…"):
            png = screenshot(t.pt_day, t.id)
        if png:
            st.image(png, width="stretch")
        else:
            st.caption("No screenshot for this turn (bash/talk turn, or day not in the export — tars end 2026-08-21).")


def page_chat():
    st.header("Chat")
    rooms = q("SELECT id::VARCHAR AS id, name FROM chat_rooms ORDER BY name")
    c1, c2, c3 = st.columns([2, 2, 3])
    room = c1.selectbox("Room", ["(all)"] + rooms.name.tolist(), index=1 + rooms.name.tolist().index("general"))
    day = c2.date_input("Day (PT)", value=pd.Timestamp("2026-09-18"))
    search = c3.text_input("Search text (all days when set)")
    where, params = [], []
    if room != "(all)":
        where.append("m.room_id = ?")
        params.append(rooms[rooms.name == room].id.iloc[0])
    if search:
        where.append("m.content ILIKE ?")
        params.append(f"%{search}%")
    else:
        where.append("(timezone('America/Los_Angeles', m.created_at::TIMESTAMPTZ))::DATE = ?")
        params.append(day)
    df = q(f"""SELECT m.created_at, m.speaker_type, a.name AS agent, m.content FROM chat_messages m
               LEFT JOIN agents a ON a.id::VARCHAR = m.agent_speaker_id
               WHERE {' AND '.join(where)} ORDER BY m.created_at LIMIT 2000""", params)
    st.caption(f"{len(df):,} messages (max 2,000 shown)")
    for _, r in df.iterrows():
        who = r.agent if r.speaker_type == "agent" else "👤 human"
        st.markdown(f"<small>{r.created_at:%m-%d %H:%M:%S} UTC</small> **{who}**", unsafe_allow_html=True)
        st.write(r.content)


def page_day():
    st.header("Day timeline")
    day = st.date_input("Day (PT)", value=pd.Timestamp("2026-09-18"))
    types = q("SELECT DISTINCT action_type FROM events_slim ORDER BY 1").action_type.tolist()
    keep = st.multiselect("Event types", types, default=[t for t in types if t not in ("WAIT", "PAUSE", "USER_NAME_CHANGE")])
    df = q("""SELECT e.created_at, e.action_type, coalesce(a.name, e.speaker_name) AS who, e.text, e.session_id
              FROM events_slim e LEFT JOIN agents a ON a.id::VARCHAR = e.agent_id
              WHERE e.pt_day = ? AND list_contains(?, e.action_type) ORDER BY e.event_index""", [day, keep])
    st.caption(f"{len(df):,} events")
    st.dataframe(df, width="stretch", hide_index=True, height=700)


TRACE = "/data/trace"
EVIDENCE_HELP = {
    "explicit": "adopter's first use names the source agent",
    "temporal": "source posted it in chat within 72 h before",
    "stale": "a prior chat post exists, but older than 72 h",
    "mention": "no visible prior URL post, but someone named its URL slug in chat within 60 min before",
    "cross_room": "eligible prior candidates exist, but their rooms were not visible to the adopter",
    "none": "no earlier visible public post — independent discovery or an unseen channel",
}


def fmt_lag(s):
    if s is None or pd.isna(s):
        return "—"
    s = float(s)
    return f"{s / 60:.0f} min" if s < 3600 else f"{s / 3600:.1f} h" if s < 172800 else f"{s / 86400:.1f} d"


def row_evidence(channel, row_id, url):
    """The text that proves one side of an edge: chat message, turn (decoded), or memory snippet around the URL."""
    if channel == "chat":
        r = q("SELECT created_at, content FROM chat_messages WHERE id = ?", [row_id])
        return None if r.empty else (r.created_at.iloc[0], [("text", r.content.iloc[0])])
    if channel in ("action", "model_output"):
        r = q("SELECT created_at, agent_action, agent_messages FROM computer_use_turns WHERE id = ?", [row_id])
        if r.empty:
            return None
        parts = decode_messages(r.agent_messages.iloc[0])
        if r.agent_action.iloc[0]:
            parts.append(("action", json.dumps(json.loads(r.agent_action.iloc[0]), indent=1)[:3000]))
        return r.created_at.iloc[0], parts
    if channel == "memory":
        r = q("SELECT created_at, content FROM agent_memories WHERE id = ?", [row_id])
        if r.empty:
            return None
        text = r.content.iloc[0]
        # The tracer stores canonical URLs; the memory may hold a variant (www./m., .git, youtu.be, http).
        keys = [url, url.split("://", 1)[-1], url.split("v=")[-1] if "youtube.com/watch" in url else url.rsplit("/", 1)[-1]]
        i = next((text.find(k) for k in keys if k and text.find(k) >= 0), -1)
        return r.created_at.iloc[0], [("memory", ("…" if i > 600 else "") + text[max(0, i - 600): i + 600] + "…")]
    return None


def show_evidence(title, actor, channel, row_id, url):
    st.markdown(f"**{title}** — {actor} · `{channel}` · row `{row_id}`")
    ev = row_evidence(channel, row_id, url)
    if ev is None:
        st.caption("Row not found.")
        return
    st.caption(f"{ev[0]:%Y-%m-%d %H:%M:%S} UTC")
    for kind, text in ev[1]:
        if kind == "reasoning":
            with st.expander("💭 reasoning"):
                st.write(text)
        elif kind in ("action", "tool"):
            st.code(text[:3000])
        else:
            st.write(text[:4000])


def page_trace():
    st.header("Trace: how a URL spread through the village")
    if not os.path.exists(f"{TRACE}/trace_artifacts.parquet"):
        st.warning("Tracer output not found — run explorer/tracer.py on this box.")
        return
    names = agent_names()
    art = q(f"SELECT * FROM read_parquet('{TRACE}/trace_artifacts.parquet') WHERE adopters IS NOT NULL")
    c1, c2, c3 = st.columns([3, 3, 2])
    search = c1.text_input("URL contains")
    origins = sorted(art.origin.dropna().unique().tolist())
    keep = c2.multiselect("Origin", origins, default=[o for o in origins if o != "noise"])
    min_adopt = c3.number_input("Min adopters", 1, 100, 5)
    view = art[art.origin.isin(keep) & (art.adopters >= min_adopt)]
    if search:
        view = view[view.url.str.contains(search, case=False, regex=False)]
    view = view.sort_values(["ev_explicit", "adopters"], ascending=False)
    st.caption(f"{len(view):,} of {len(art):,} traced URLs · evidence: " +
               " · ".join(f"**{k}** = {v}" for k, v in EVIDENCE_HELP.items()))
    table = view[["url", "origin", "adopters", "ev_explicit", "ev_temporal", "ev_mention", "ev_stale", "ev_cross_room", "ev_none",
                  "median_lag_s", "first_at", "first_actor"]].copy()
    table["first_actor"] = table.first_actor.map(lambda a: names.get(a, a))
    table["median_lag"] = table.pop("median_lag_s").map(fmt_lag)
    pick = st.dataframe(table, width="stretch", hide_index=True, height=300,
                        on_select="rerun", selection_mode="single-row")
    rows_sel = pick.selection.rows if pick and pick.selection else []
    # A trace can also be opened directly with ?url=<canonical url> (linkable from the write-up).
    url = table.iloc[rows_sel[0]].url if rows_sel else st.query_params.get("url")
    if not url or url not in set(art.url):
        st.info("Select a URL above to see its spread.")
        return
    st.query_params["url"] = url
    view = art[art.url == url]
    a = view[view.url == url].iloc[0]
    st.subheader(url)
    st.markdown(f"Origin **{a.origin}** · first used by **{names.get(a.first_actor, a.first_actor)}** in "
                f"`{a.first_channel}` at {a.first_at:%Y-%m-%d %H:%M} UTC · {int(a.adopters)} adopters")

    uses = q(f"SELECT actor, is_human, channel, first_at, row_id, n FROM read_parquet('{TRACE}/trace_first_use.parquet') "
             "WHERE url = ? ORDER BY first_at", [url])
    uses["who"] = uses.actor.map(lambda x: names.get(x, x))
    st.altair_chart(alt.Chart(uses).mark_circle(size=90).encode(
        x=alt.X("first_at:T", title="first use"), y=alt.Y("who:N", sort=None, title=None),
        color=alt.Color("channel:N"), tooltip=["who", "channel", "first_at:T", "n", "row_id"]
    ).properties(height=max(200, 22 * uses.who.nunique())), width="stretch")

    edges = q(f"SELECT * FROM read_parquet('{TRACE}/trace_edges_scored.parquet') WHERE url = ? ORDER BY t_at", [url])
    edges["adopter"] = edges.target.map(lambda x: names.get(x, x))
    edges["from"] = edges.source.map(lambda x: names.get(x, x) if isinstance(x, str) else "—")
    edges["lag"] = edges.lag_s.map(fmt_lag)
    et = edges[["t_at", "adopter", "target_channel", "from", "lag", "evidence", "prior_posts",
                "dropped_candidates", "room_unknown"]]
    st.markdown("**Exposure edges**")
    st.dataframe(et, width="stretch", hide_index=True)
    if edges.empty:
        return
    order = edges.evidence.map({"explicit": 0, "temporal": 1, "mention": 2, "stale": 3,
                                "cross_room": 4, "none": 5}).sort_values(kind="stable").index
    i = st.selectbox("Inspect edge", list(order), format_func=lambda k:
                     f"{edges.adopter[k]} ← {edges['from'][k]} · {edges.evidence[k]} · {fmt_lag(edges.lag_s[k])}")
    e = edges.loc[i]
    st.caption(f"Evidence: **{e.evidence}** — {EVIDENCE_HELP[e.evidence]}")
    if e.room_unknown:
        st.caption("Adopter room history is missing or the selected source room is unknown; visibility is unverified.")
    if e.dropped_candidates:
        st.caption(f"{int(e.dropped_candidates)} prior candidate posts were excluded by room visibility.")
    l, r = st.columns(2)
    with l:
        if isinstance(e.source_row, str):
            show_evidence("Source post", e["from"], "chat", e.source_row, url)
        else:
            st.caption("No earlier public post of this URL.")
    with r:
        show_evidence("Adopter's first use", e.adopter, e.target_channel, e.target_row, url)


def page_sql():
    st.header("SQL (read-only DuckDB)")
    st.caption("Tables: agents, village_goals, agent_goals, chat_rooms, chat_messages, events, events_slim, "
               "computer_use_sessions, computer_use_turns, turns_slim, agent_memories, memories_slim, summaries, "
               "claude_code_messages, claude_code_sessions. See docs/DATA_PROFILE.md.")
    sql = st.text_area("Query", height=160, value=
        "SELECT a.name, count(*) AS bash_turns\nFROM turns_slim t JOIN agents a ON a.id::VARCHAR = t.agent_id\n"
        "WHERE t.action = 'bash'\nGROUP BY 1 ORDER BY 2 DESC LIMIT 20")
    if st.button("Run"):
        try:
            st.dataframe(q(sql), width="stretch", hide_index=True)
        except Exception as e:
            st.error(str(e))


PAGES = {"Overview": page_overview, "Trace": page_trace, "Agent": page_agent, "Session replay": page_session,
         "Chat": page_chat, "Day timeline": page_day, "SQL": page_sql}
st.sidebar.title("AI Village explorer")
st.sidebar.caption("Private · data stays on this box · rev 838b415")
PAGES[st.sidebar.radio("View", list(PAGES))]()
