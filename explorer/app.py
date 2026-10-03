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
    "explicit": "adopter names the source; no self-discovery cue detected (not proof of receipt)",
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
    columns = ["t_at", "adopter", "target_channel", "from", "lag", "evidence", "prior_posts",
               "dropped_candidates", "room_unknown"]
    columns += [c for c in ("source_named", "self_found", "self_found_cues", "named_old") if c in edges]
    et = edges[columns]
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
    if e.get("self_found", False):
        st.caption("Possible self-discovery: " + ", ".join(e.self_found_cues) +
                   ". Naming the source does not establish receipt; inspect the adopter text.")
    if e.get("named_old", False):
        st.caption("Named source is more than 72 h old. Age alone does not establish exposure.")
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


F1_URL = "https://gitlab.com/ai-village-agents/village/graffiti-verification"
FINDINGS = "/data/findings"
SPREAD_FRAMES_S = [0, 60, 120, 240, 480, 900, 1800, 3600, 2 * 3600, 4 * 3600, 8 * 3600, 12 * 3600,
                   86400, 2 * 86400, 4 * 86400, 7 * 86400, 14 * 86400, 42 * 86400]
STAGE_COLOR = {"not yet": "#d0d4da", "mentioned it": "#f2c14e", "saved to memory": "#f08a3c",
               "acted on it": "#d1495b", "origin": "#6a4c93"}


def fmt_offset(s):
    s = int(s)
    return "start" if s == 0 else f"+{s // 60} min" if s < 3600 else f"+{s // 3600} h" if s < 172800 else f"+{s // 86400} days"


def page_spread():
    """Animated 'village' view: who picked a link up, from whom, and how far it got (hook for first-time viewers)."""
    import math
    import plotly.graph_objects as go

    st.header("Watch it spread")
    st.caption("Each dot is an AI agent in the village. Press ▶ to watch one link travel from agent to agent. "
               "Colour = how far it got into that agent: mentioned it → saved it to memory → acted on it. "
               "Lines = the exposure the tracer found (solid: the adopter named the source; thin: timing only).")
    url = st.text_input("Link to follow", value=st.query_params.get("url", F1_URL))
    names = agent_names()
    uses = q(f"SELECT actor, channel, first_at FROM read_parquet('{TRACE}/trace_first_use.parquet') "
             "WHERE url = ? AND NOT is_human", [url])
    if uses.empty:
        st.warning("No agent used this link.")
        return
    t0 = uses.first_at.min()
    origin = uses.sort_values("first_at").actor.iloc[0]
    # The village at that moment: everyone who used the link, plus every agent active in the week around it.
    active = q("SELECT DISTINCT agent_id FROM turns_slim WHERE created_at BETWEEN ? AND ?",
               [t0 - pd.Timedelta(days=1), t0 + pd.Timedelta(days=7)]).agent_id.tolist()
    ring = sorted(set(active) | set(uses.actor), key=lambda a: names.get(a, a))
    pos = {a: (math.cos(2 * math.pi * i / len(ring)), math.sin(2 * math.pi * i / len(ring))) for i, a in enumerate(ring)}
    edges = q(f"SELECT source, target, t_at, evidence FROM read_parquet('{TRACE}/trace_edges_scored.parquet') "
              "WHERE url = ? AND evidence IN ('explicit', 'temporal', 'mention')", [url])
    edges = edges[edges.source.isin(pos) & edges.target.isin(pos)]
    rank = {"model_output": 1, "chat": 1, "memory": 2, "action": 3}
    label = {1: "mentioned it", 2: "saved to memory", 3: "acted on it"}

    def stage(agent, until):
        if agent == origin:
            return "origin"
        got = uses[(uses.actor == agent) & (uses.first_at <= until)]
        return label[max(rank[c] for c in got.channel)] if len(got) else "not yet"

    def frame_traces(offset_s):
        until = t0 + pd.Timedelta(seconds=offset_s)
        traces = []
        for ev, width, color in (("explicit", 2.2, "#3a3a3a"), ("temporal", 0.8, "#9aa0a6"), ("mention", 0.8, "#c9b6e4")):
            xs, ys = [], []
            for e in edges[(edges.evidence == ev) & (edges.t_at <= until)].itertuples():
                (x0, y0), (x1, y1) = pos[e.source], pos[e.target]
                xs += [x0, x1, None]
                ys += [y0, y1, None]
            traces.append(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=width, color=color),
                                     hoverinfo="skip", name=ev))
        stages = [stage(a, until) for a in ring]
        reached = sum(s != "not yet" for s in stages)
        traces.append(go.Scatter(
            x=[pos[a][0] for a in ring], y=[pos[a][1] for a in ring], mode="markers+text",
            marker=dict(size=[26 if s == "origin" else 18 for s in stages], color=[STAGE_COLOR[s] for s in stages],
                        line=dict(width=1, color="#555")),
            text=[names.get(a, a).replace("Claude ", "") for a in ring], textposition="top center",
            textfont=dict(size=11, color="#222"), hovertext=[f"{names.get(a, a)}: {s}" for a, s in zip(ring, stages)],
            hoverinfo="text", name="agents"))
        return traces, reached

    frames, steps = [], []
    for off in SPREAD_FRAMES_S:
        tr, reached = frame_traces(off)
        name = fmt_offset(off)
        frames.append(go.Frame(data=tr, name=name,
                               layout=go.Layout(title=f"{name}   ·   reached {reached} of {len(ring)} agents")))
        steps.append(dict(method="animate", label=name,
                          args=[[name], dict(mode="immediate", frame=dict(duration=0, redraw=True))]))
    first, reached0 = frame_traces(0)
    fig = go.Figure(data=first, frames=frames)
    fig.update_layout(
        title=f"start   ·   reached {reached0} of {len(ring)} agents", height=720, showlegend=False,
        xaxis=dict(visible=False, range=[-1.35, 1.35]), yaxis=dict(visible=False, range=[-1.25, 1.3], scaleanchor="x"),
        margin=dict(l=10, r=10, t=60, b=90), plot_bgcolor="white", paper_bgcolor="white",
        title_font=dict(color="#222"),
        updatemenus=[dict(type="buttons", direction="left", x=0.0, xanchor="left", y=-0.02, yanchor="top",
                          showactive=False, buttons=[
            dict(label="▶ play", method="animate",
                 args=[None, dict(frame=dict(duration=900, redraw=True), fromcurrent=True, transition=dict(duration=300))]),
            dict(label="❚❚ pause", method="animate",
                 args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])])],
        sliders=[dict(active=0, steps=steps, x=0.2, len=0.8, y=-0.02, yanchor="top",
                      currentvalue=dict(prefix="time since first use: "))])
    st.plotly_chart(fig, width="stretch")
    legend = "  ".join(f"<span style='color:{c}'>●</span> {k}" for k, c in STAGE_COLOR.items())
    st.markdown(legend, unsafe_allow_html=True)
    st.caption(f"First use: {names.get(origin, origin)} at {t0:%Y-%m-%d %H:%M} UTC. "
               "Time steps are uneven on purpose — most spreading happens in the first hours.")


CHANNEL_WORD = {"chat": "repeated it in chat", "model_output": "repeated it in its reasoning",
                "memory": "saved it to memory", "action": "acted on it"}
CASCADE_FRAMES_MIN = [1, 2, 5, 10, 30, 60, 180, 360, 720, 1440, 1590, 2160, 2880]


def fmt_minutes(m):
    if m < 1:
        return "<1 min"
    if m < 60:
        return f"{m:.0f} min"
    if m < 48 * 60:
        return f"{m / 60:.1f} h"
    return f"{m / 1440:.1f} days"


def page_cascade():
    """Finding 1 as one story: who repeated the claim, how fast, and when anyone first checked it."""
    import math
    import plotly.graph_objects as go

    if not os.path.exists(f"{FINDINGS}/f1_verify.parquet"):
        st.warning("Run explorer/findings.py on this box first.")
        return
    names = agent_names()
    short = lambda n: n.replace("Claude ", "")  # noqa: E731
    moments = q(f"SELECT * FROM read_parquet('{FINDINGS}/f1_moments.parquet') ORDER BY created_at")
    t0 = moments.created_at.min()  # Opus 5's announcement (chat eb0a037a)
    author = {a for a, n in names.items() if n == "Claude Opus 5"}
    uses = q(f"SELECT actor, channel, first_at, row_id FROM read_parquet('{TRACE}/trace_first_use.parquet') "
             "WHERE url = ? AND NOT is_human", [F1_URL])
    rep = (uses[~uses.actor.isin(author) & (uses.first_at >= t0)].sort_values("first_at")
           .groupby("actor", as_index=False).head(1))
    rep = rep.assign(name=rep.actor.map(lambda a: names.get(a, a)),
                     m=(rep.first_at - t0).dt.total_seconds() / 60)
    ver = q(f"SELECT agent AS name, created_at, row_id FROM read_parquet('{FINDINGS}/f1_verify.parquet') "
            "WHERE status = 'success' ORDER BY created_at")
    ver = ver[ver.created_at >= t0].groupby("name", as_index=False).head(1)
    ver = ver.assign(m=(ver.created_at - t0).dt.total_seconds() / 60)
    horizon = 48 * 60
    first_check = ver.m.min()
    n1h = int((rep.m <= 60).sum())
    n_before = int((rep.m < first_check).sum())

    st.markdown(f"<div style='font-size:2.0rem;font-weight:700;line-height:1.25'>One AI announced a maths "
                f"breakthrough. <span style='color:#ff5c6c'>{n1h} others repeated it within an hour.</span><br>"
                f"<span style='color:#3ddc97'>The first independent check came {first_check / 60:.1f} hours later.</span>"
                f"</div>", unsafe_allow_html=True)
    st.markdown(f"Claude Opus 5 posted *\"two open conjectures … are now **disproved**\"* with verifier scripts "
                f"({t0:%b %d, %H:%M} UTC). By the time any other agent ran a verifier successfully, "
                f"**{n_before} agents** had already passed the claim on: in chat, in their notes, in news articles.")

    late = int((rep.m > horizon).sum())
    rep, ver = rep[rep.m <= horizon], ver[ver.m <= horizon]  # draw the first 48 h only; later repeats are counted below
    rows = list(rep.name) + [n for n in ver.name if n not in set(rep.name)]
    y = {n: i + 1 for i, n in enumerate(rows)}
    ylabels = ["Opus 5 (author)"] + [short(n) for n in rows]
    x_of = lambda m: max(m, 0.5)  # noqa: E731  log axis: put sub-minute events at 30 s

    def traces(until_m):
        r = rep[rep.m <= until_m]
        v = ver[ver.m <= until_m]
        out = [go.Scatter(x=[0.5], y=[0], mode="markers", marker=dict(symbol="star", size=22, color="#b28dff"),
                          hovertext=[f"Claude Opus 5 announces the disproofs<br>{t0:%Y-%m-%d %H:%M} UTC<br>chat eb0a037a"],
                          hoverinfo="text", name="announcement"),
               go.Scatter(x=[x_of(m) for m in r.m], y=[y[n] for n in r.name], mode="markers",
                          marker=dict(size=13, color="#ff5c6c", line=dict(width=1, color="#ffffff")),
                          hovertext=[f"<b>{n}</b><br>+{fmt_minutes(m)}: {CHANNEL_WORD.get(c, c)}<br>row {rid[:8]}"
                                     for n, m, c, rid in zip(r.name, r.m, r.channel, r.row_id)],
                          hoverinfo="text", name="repeated the claim"),
               go.Scatter(x=[x_of(m) for m in v.m], y=[y[n] for n in v.name], mode="markers+text",
                          marker=dict(symbol="diamond", size=15, color="#3ddc97", line=dict(width=1, color="#ffffff")),
                          text=["✔"] * len(v), textposition="middle right", textfont=dict(color="#3ddc97", size=14),
                          hovertext=[f"<b>{n}</b><br>+{fmt_minutes(m)}: ran a verifier, success signal<br>row {rid[:8]}"
                                     for n, m, rid in zip(v.name, v.m, v.row_id)],
                          hoverinfo="text", name="checked it (verifier passed)")]
        return out

    def shapes(until_m):
        end = min(until_m, first_check)
        sh = [dict(type="rect", xref="x", yref="paper", x0=0.5, x1=x_of(end), y0=0, y1=1,
                   fillcolor="rgba(255,92,108,0.10)", line=dict(width=0), layer="below"),
              dict(type="line", xref="x", yref="paper", x0=x_of(until_m), x1=x_of(until_m), y0=0, y1=1,
                   line=dict(color="rgba(255,255,255,0.35)", width=1, dash="dot"))]
        if until_m >= 60:
            sh.append(dict(type="line", xref="x", yref="paper", x0=60, x1=60, y0=0, y1=1,
                           line=dict(color="#ff5c6c", width=1, dash="dash")))
        if until_m >= first_check:
            sh.append(dict(type="line", xref="x", yref="paper", x0=first_check, x1=first_check, y0=0, y1=1,
                           line=dict(color="#3ddc97", width=2)))
        return sh

    def notes(until_m):
        a = []
        if until_m >= 60:
            a.append(dict(x=1.778, xref="x", y=1.02, yref="paper", text=f"1 hour: {n1h} repeats",
                          showarrow=False, font=dict(color="#ff5c6c", size=13), xanchor="center"))
        if until_m >= first_check:
            a.append(dict(x=math.log10(first_check), xref="x", y=1.02, yref="paper",
                          text=f"first real check: +{first_check / 60:.1f} h", showarrow=False,
                          font=dict(color="#3ddc97", size=13), xanchor="center"))
        a.append(dict(x=0.02, xref="paper", y=0.02, yref="paper", text="unchecked window", showarrow=False,
                      font=dict(color="rgba(255,92,108,0.7)", size=12), xanchor="left"))
        last_rep = rep.m[rep.m < first_check].max()
        if until_m >= last_rep + 60:
            gap_x = (math.log10(last_rep) + math.log10(first_check)) / 2
            a.append(dict(x=gap_x, xref="x", y=0.45, yref="paper", showarrow=False, align="center",
                          text=f"<b>{(first_check - last_rep) / 60:.0f} hours: no new repeats, no checks</b><br>"
                               f"{n_before} agents had already passed it on.<br>Nobody had run the verifier.",
                          font=dict(color="rgba(255,255,255,0.8)", size=14)))
        return a

    def title(until_m):
        r = int((rep.m <= until_m).sum())
        v = int((ver.m <= until_m).sum())
        return f"+{fmt_minutes(until_m)}   ·   {r} agents repeated it   ·   {v} checked it"

    frames = [go.Frame(data=traces(t), name=fmt_minutes(t),
                       layout=go.Layout(shapes=shapes(t), annotations=notes(t), title=dict(text=title(t))))
              for t in CASCADE_FRAMES_MIN]
    ticks = [1, 5, 15, 60, 180, 720, 1440, 2880]
    fig = go.Figure(data=traces(horizon), frames=frames)
    fig.update_layout(
        height=max(520, 26 * len(ylabels) + 160), template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        title=dict(text=title(horizon), font=dict(size=15), x=0.01, xanchor="left"), shapes=shapes(horizon),
        annotations=notes(horizon),
        xaxis=dict(type="log", range=[-0.35, 3.55], tickvals=ticks,
                   ticktext=["1 min", "5 min", "15 min", "1 h", "3 h", "12 h", "1 day", "2 days"],
                   title="time since the announcement (log scale)", gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(tickvals=list(range(len(ylabels))), ticktext=ylabels, autorange="reversed",
                   gridcolor="rgba(255,255,255,0.05)"),
        legend=dict(orientation="h", y=-0.10, x=0.14, yanchor="top"), margin=dict(l=10, r=30, t=70, b=120),
        updatemenus=[dict(type="buttons", direction="left", x=0, xanchor="left", y=-0.10, yanchor="top",
                          bgcolor="#ff5c6c", font=dict(color="#ffffff", size=14), showactive=False, buttons=[
            dict(label="▶  replay", method="animate",
                 args=[[fmt_minutes(t) for t in CASCADE_FRAMES_MIN],
                       dict(frame=dict(duration=700, redraw=True), transition=dict(duration=250), mode="immediate")])])])
    st.plotly_chart(fig, width="stretch")
    st.caption("Red: the first time each agent used the claim's link (chat, reasoning, memory or an action). "
               "Green ✔: the first time each other agent ran one of Opus 5's verify_conj*.py scripts with a success "
               "signal in the output (a keyword heuristic, not proof the maths was checked). Hover any mark for the "
               f"dataset row behind it. Shown: first 48 h; {late} later repeats not drawn. "
               "Method and caveats: docs/FINDINGS.md §1.")



# ------------------------------------------------------------------ belief graph
BELIEF_JSON = f"{FINDINGS}/belief_graffiti.json"


def _belief_graph_url(url):
    """Temporary builder (issue #26 contract) for a URL seed; replaced by explorer/belief_graph.py when it lands."""
    names = agent_names()
    uses = q(f"SELECT actor, channel, first_at, row_id FROM read_parquet('{TRACE}/trace_first_use.parquet') "
             "WHERE url = ? AND NOT is_human ORDER BY first_at", [url])
    edges = q(f"SELECT source, target, t_at, evidence, source_row, target_row FROM "
              f"read_parquet('{TRACE}/trace_edges_scored.parquet') WHERE url = ? "
              "AND evidence IN ('explicit', 'temporal', 'mention') ORDER BY t_at", [url])
    t0 = uses.first_at.min()
    iso = lambda t: pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%S")  # noqa: E731
    nodes = [{"id": f"artifact:{url}", "kind": "artifact", "label": url.split("/")[-1] or url, "first_at": iso(t0)}]
    seen = set()
    out = []
    for r in uses.itertuples():
        a = f"agent:{r.actor}"
        if a not in seen:
            seen.add(a)
            nodes.append({"id": a, "kind": "agent", "label": names.get(r.actor, r.actor), "first_at": iso(r.first_at)})
        kind = "said" if r.channel in ("chat", "model_output") else "did"
        out.append({"id": f"{kind}:{r.row_id}", "kind": kind, "source": a, "target": f"artifact:{url}",
                    "at": iso(r.first_at), "channel": r.channel, "row": r.row_id})
    for e in edges.itertuples():
        out.append({"id": f"told:{e.source_row}:{e.target_row}", "kind": "told", "source": f"agent:{e.source}",
                    "target": f"agent:{e.target}", "at": iso(e.t_at), "evidence": e.evidence,
                    "rows": [e.source_row, e.target_row]})
    if url == F1_URL and os.path.exists(f"{FINDINGS}/f1_verify.parquet"):
        by_name = {v: k for k, v in names.items()}
        ver = q(f"SELECT agent, created_at, row_id, status FROM read_parquet('{FINDINGS}/f1_verify.parquet') ORDER BY created_at")
        for r in ver.itertuples():
            a = f"agent:{by_name.get(r.agent, r.agent)}"
            if a not in seen:
                seen.add(a)
                nodes.append({"id": a, "kind": "agent", "label": r.agent, "first_at": iso(r.created_at)})
            out.append({"id": f"checked:{r.row_id}", "kind": "checked", "source": a, "target": f"artifact:{url}",
                        "at": iso(r.created_at), "row": r.row_id, "basis": "verifier",
                        "status": {"success": "supported", "fail": "contradicted"}.get(r.status, "unknown")})
    out.sort(key=lambda e: (e["at"], e["id"]))
    return {"seed": {"kind": "url", "value": url, "label": url}, "t0": iso(t0), "nodes": nodes, "edges": out}


BELIEF_HTML = r"""
<div id="wrap" style="display:flex;gap:14px;font-family:Inter,system-ui,sans-serif;color:#e8e8ea">
 <div style="flex:1;min-width:0">
  <div id="hud" style="display:flex;align-items:flex-start;gap:14px;margin:0 0 4px 4px">
   <button id="play" style="background:#ff5c6c;color:#fff;border:0;border-radius:6px;padding:8px 16px;font-size:15px;cursor:pointer;flex:none">▶ play</button>
   <div style="flex:1;min-width:160px">
    <input id="t" type="range" min="0" max="1000" value="1000" style="width:100%;margin:8px 0 2px 0">
    <div id="moments" style="position:relative;height:62px"></div>
   </div>
  </div>
  <div id="clock" style="font-size:15px;font-weight:600;margin:0 0 6px 4px"></div>
  <div id="net" style="height:__H__px;border-radius:10px;background:radial-gradient(circle at 50% 50%,#1b1d26 0%,#0e1117 70%)"></div>
  <div style="font-size:12.5px;color:#a9adb8;margin:6px 4px;line-height:1.6">
   Rings = time since the start (log): 1 min · 1 h · 1 day · 1 week. <b>Agents</b> are split circles:
   top = what it <b>said</b> <span id="stlegend"></span>, bottom = what it <b>did</b> (<span style="color:#f2a541">●</span> acted,
   <span style="color:#3ddc97">●</span> checked &amp; held, <span style="color:#ff5c6c">✕</span> checked &amp; failed).
   <b>Claims</b> are diamonds: <span style="color:#3ddc97">◆</span> screen backs it · <span style="color:#ff5c6c">◆ cracked</span>
   screen contradicts it · <span style="color:#d9dbe1">◇</span> not checked. Dots = links/files touched.
   Lines: <span style="color:#ff5c6c">red</span> told · <span style="color:#8a8f9c">grey</span> said/did · <span style="color:#3ddc97">green</span>/<span style="color:#ff5c6c">red</span> checked.
  </div>
 </div>
 <div id="side" style="width:290px;flex:none;background:#161922;border-radius:10px;padding:14px;font-size:13.5px;line-height:1.45;height:__H__px;overflow:auto">
  <div style="font-weight:700;font-size:15px;margin-bottom:6px">Evidence</div>
  <div id="info" style="color:#c9ccd4">Click anything to see what was said, what was done, and the dataset rows behind it.</div>
 </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/vis-network@9/standalone/umd/vis-network.min.js"></script>
<script>
const G = __DATA__;
const MOMENTS = __MOMENTS__;               // verified key moments (row ids) for this seed, shown under the slider
const D = (__DRIFT__).agents || {};      // claim drift per agent: a timeline of stances (first text + 72 h of chat)
const PRI = {neutral: 0, hedges: 1, repeats: 2, checks: 3, flags: 4, amplifies: 5, original: 6};
Object.values(D).forEach(d => { if (!d.timeline) d.timeline = [{at: d.at, stance: d.stance, gist: d.gist, cue: d.cue, row: d.row, src: "first text"}]; });
function stanceAt(id) {                  // most escalated stance among this agent's labelled texts up to NOW
  const d = D[id]; if (!d) return null; let best = null;
  d.timeline.forEach(e => { if (mins(e.at) <= NOW && (!best || PRI[e.stance] > PRI[best.stance])) best = e; });
  return best;
}
const STANCE = {original: ["#b28dff", "the original claim"], repeats: ["#ff5c6c", "repeated it"], amplifies: ["#ff2fb4", "pushed it further (more certain, published or promoted)"],
  hedges: ["#f2c14e", "passed it on with caution"], checks: ["#2ec4b6", "checked it itself"], flags: ["#4ea8ff", "flagged it as wrong"],
  neutral: ["#5b6070", "only touched the link"]};
const P = iso => Date.parse(iso.endsWith("Z") ? iso : iso + "Z");
const T0 = P(G.t0), mins = iso => (P(iso) - T0) / 60000;
const RMAX = 10080, rad = m => 80 + 330 * Math.log10(1 + Math.max(m, 0)) / Math.log10(1 + RMAX);
const fmt = m => m < 1 ? "<1 min" : m < 60 ? Math.round(m) + " min" : m < 2880 ? (m / 60).toFixed(1) + " h" : (m / 1440).toFixed(1) + " days";
const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
const centerId = G.seed.kind === "agent" ? "agent:" + G.seed.value : "artifact:" + G.seed.value;
const byId = Object.fromEntries(G.nodes.map(n => [n.id, n]));
const isClaim = n => n.kind === "artifact" && /^Claim /.test(n.label || "");
// per-node timelines
const st = {};
G.nodes.forEach(n => st[n.id] = {said: Infinity, did: Infinity, ok: Infinity, bad: Infinity, first: mins(n.first_at), edges: []});
G.edges.forEach(e => {
  const m = mins(e.at), s = st[e.source], t = st[e.target];
  if (s) s.edges.push(e); if (t && e.target !== e.source) t.edges.push(e);
  if (!s) return;
  if (e.kind === "said") s.said = Math.min(s.said, m);
  if (e.kind === "did") s.did = Math.min(s.did, m);
  if (e.kind === "checked") {
    const tgt = st[e.target];
    if (e.status === "supported") { s.ok = Math.min(s.ok, m); if (tgt) tgt.ok = Math.min(tgt.ok, m); }
    // a verifier run that errored is a run signal, not evidence the claim is false: keep it out of 'contradicted'
    if (e.status === "contradicted" && e.basis === "verifier") s.err = Math.min(s.err ?? Infinity, m);
    else if (e.status === "contradicted") { s.bad = Math.min(s.bad, m); if (tgt) tgt.bad = Math.min(tgt.bad, m); }
  }
});
// layout: centre fixed, others on log-time rings by first appearance, golden angle, agents first
const others = G.nodes.filter(n => n.id !== centerId).sort((a, b) => (a.kind === b.kind ? 0 : a.kind === "agent" ? -1 : 1) || st[a.id].first - st[b.id].first);
const pos = {[centerId]: {x: 0, y: 0}};
others.forEach((n, i) => { const ang = i * 2.39996 + (n.kind === "agent" ? 0 : 0.6); const r = rad(st[n.id].first); pos[n.id] = {x: r * Math.cos(ang), y: r * Math.sin(ang)}; });
const ALL = 1e12; let NOW = ALL;           // 'all time' must stay finite: Infinity <= Infinity is true
const on = m => m <= NOW;
function agentColors(id) {
  const s = st[id], touched = on(s.said) || on(s.did) || on(s.ok) || on(s.bad);
  const sa = stanceAt(id), top = !touched && !sa ? "#3a3f4b" : D[id] ? STANCE[(sa || {stance: "neutral"}).stance]?.[0] || "#ff5c6c" : "#ff5c6c";
  let bot = "#3a3f4b", crack = false;
  if (on(s.did)) bot = "#f2a541";
  if (on(s.ok)) bot = "#3ddc97";
  if (on(s.bad) && !on(s.ok)) { bot = "#ff5c6c"; crack = true; }
  if (on(s.bad) && on(s.ok)) crack = true;   // has both a held-up and a failed check: green with a crack
  return {top, bot, crack, lit: top !== "#3a3f4b" || bot !== "#3a3f4b" || on(s.first)};
}
const short = l => (l || "").replace("Claude ", "");
function agentRenderer({ctx, id, x, y, state: {selected, hover}, label}) {
  return {drawNode() {
    const c = agentColors(id), big = id === centerId, R0 = big ? 24 : 15, r = selected || hover ? R0 + 3 : R0;
    ctx.save(); ctx.globalAlpha = c.lit ? 1 : 0.35;
    ctx.beginPath(); ctx.arc(x, y, r, Math.PI, 0); ctx.closePath(); ctx.fillStyle = c.top; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI); ctx.closePath(); ctx.fillStyle = c.bot; ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - r, y); ctx.lineTo(x + r, y); ctx.strokeStyle = "#0e1117"; ctx.lineWidth = 2; ctx.stroke();
    ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.strokeStyle = selected || big ? "#ffffff" : "rgba(255,255,255,0.55)"; ctx.lineWidth = selected || big ? 2.5 : 1; ctx.stroke();
    if (c.crack) { ctx.beginPath(); ctx.moveTo(x - r * .4, y + 3); ctx.lineTo(x - r * .05, y + r * .6); ctx.lineTo(x + r * .2, y + r * .25); ctx.lineTo(x + r * .45, y + r * .75); ctx.strokeStyle = "#0e1117"; ctx.lineWidth = 2; ctx.stroke(); }
    ctx.fillStyle = "#e8e8ea"; ctx.font = (big ? "bold 15px" : "13px") + " Inter, sans-serif"; ctx.textAlign = "center";
    ctx.fillText(label, x, y + r + 15); ctx.restore();
  }, nodeDimensions: {width: 2 * R, height: 2 * R}};
}
const R = 15;
function claimRenderer({ctx, id, x, y, state: {selected, hover}}) {
  const s = st[id], big = id === centerId, r = (big ? 22 : 11) + (selected || hover ? 3 : 0);
  return {drawNode() {
    const col = on(s.bad) ? "#ff5c6c" : on(s.ok) ? "#3ddc97" : "#d9dbe1";
    ctx.save(); ctx.globalAlpha = on(s.first) ? 1 : 0.3;
    ctx.beginPath(); ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath();
    ctx.fillStyle = col; ctx.fill(); ctx.strokeStyle = selected ? "#ffffff" : "#0e1117"; ctx.lineWidth = selected ? 2.5 : 1.5; ctx.stroke();
    if (on(s.bad)) { ctx.beginPath(); ctx.moveTo(x - r * .5, y - r * .2); ctx.lineTo(x - r * .1, y + r * .25); ctx.lineTo(x + r * .15, y - r * .1); ctx.lineTo(x + r * .5, y + r * .35); ctx.strokeStyle = "#0e1117"; ctx.lineWidth = 2; ctx.stroke(); }
    if (big || selected || hover) { ctx.fillStyle = "#e8e8ea"; ctx.font = (big ? "bold 14px" : "11px") + " Inter, sans-serif"; ctx.textAlign = "center"; ctx.fillText(big ? "the claim" : "claim", x, y + r + 14); }
    ctx.restore();
  }, nodeDimensions: {width: 2 * r, height: 2 * r}};
}
const visNodes = G.nodes.map(n => {
  const base = {id: n.id, fixed: true, x: pos[n.id].x, y: pos[n.id].y};
  if (n.kind === "agent") return {...base, label: short(n.label), shape: "custom", ctxRenderer: agentRenderer};
  if (isClaim(n)) return {...base, shape: "custom", ctxRenderer: claimRenderer};
  if (n.id === centerId) return {...base, label: G.seed.kind === "url" ? "the link" : "artifact", shape: "star", size: 26, color: {background: "#b28dff", border: "#ffffff"}, font: {color: "#e8e8ea", size: 14, vadjust: -6}};
  return {...base, shape: "dot", size: 4, color: {background: "#8a8f9c", border: "#8a8f9c"}, title: n.label};
});
const nodes = new vis.DataSet(visNodes);
// edges: one best incoming 'told' per agent; said/did/checked edges only between drawn nodes; in big graphs drop said/did to links
const rankEv = {explicit: 0, temporal: 1, mention: 2}, bestIn = {};
G.edges.filter(e => e.kind === "told" && st[e.source] && st[e.target] && e.source !== e.target).forEach(e => {
  const k = e.target + "|" + (e.artifact || ""), b = bestIn[k];
  if (!b || rankEv[e.evidence] < rankEv[b.evidence] || (rankEv[e.evidence] === rankEv[b.evidence] && e.at < b.at)) bestIn[k] = e;
});
const told = Object.values(bestIn);
const sayDo = G.edges.filter(e => (e.kind === "said" || e.kind === "did") && st[e.source] && st[e.target] && (isClaim(byId[e.target]) || G.nodes.length <= 40 || e.target === centerId));
const checks = G.edges.filter(e => e.kind === "checked" && st[e.source] && st[e.target]);
const drawn = [].concat(
  told.map(e => ({id: e.id, from: e.source, to: e.target, kind: "told", at: e.at, arrows: {to: {enabled: true, scaleFactor: 0.5}}, width: e.evidence === "explicit" ? 2.6 : 0.9, dashes: e.evidence === "mention", color: {color: "rgba(255,92,108,0.6)", highlight: "#ffffff"}, smooth: {type: "curvedCW", roundness: 0.15}})),
  sayDo.map(e => ({id: e.id, from: e.source, to: e.target, kind: e.kind, at: e.at, width: 0.6, color: {color: "rgba(138,143,156,0.35)", highlight: "#ffffff"}, smooth: false})),
  checks.map(e => ({id: e.id, from: e.source, to: e.target, kind: "checked", at: e.at, width: 2.4, color: {color: e.status === "contradicted" ? "#ff5c6c" : e.status === "supported" ? "#3ddc97" : "rgba(217,219,225,0.5)", highlight: "#ffffff"}, dashes: e.status === "unknown", smooth: false})));
const edges = new vis.DataSet(drawn);
const net = new vis.Network(document.getElementById("net"), {nodes, edges}, {physics: false, interaction: {hover: true, zoomView: true, tooltipDelay: 80}});
net.on("beforeDrawing", ctx => {
  [[1, "1 min"], [60, "1 h"], [1440, "1 day"], [RMAX, "1 week"]].forEach(([m, t]) => {
    const r = rad(m); ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.strokeStyle = "rgba(255,255,255,0.10)"; ctx.setLineDash([4, 6]); ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "rgba(255,255,255,0.40)"; ctx.font = "12px Inter"; ctx.fillText(t, r + 4, -4);
  });
  if (NOW < ALL) { const r = rad(NOW); ctx.beginPath(); ctx.arc(0, 0, r, 0, 2 * Math.PI); ctx.strokeStyle = "rgba(255,92,108,0.35)"; ctx.lineWidth = 2; ctx.stroke(); }
});
const sl = document.getElementById("t"), clock = document.getElementById("clock");
const toM = v => Math.pow(10, v / 1000 * Math.log10(1 + RMAX)) - 1;
const agents = G.nodes.filter(n => n.kind === "agent");
function update(v) {
  NOW = v >= 1000 ? ALL : toM(v);
  edges.update(drawn.map(e => ({id: e.id, hidden: mins(e.at) > NOW})));
  const believed = agents.filter(a => [st[a.id].said, st[a.id].did, st[a.id].ok, st[a.id].bad].some(on)).length;
  const ok = agents.filter(a => on(st[a.id].ok)).length;
  const bad = G.nodes.filter(n => isClaim(n) && on(st[n.id].bad)).length;
  const okClaims = G.nodes.filter(n => isClaim(n) && on(st[n.id].ok)).length;
  const lit = agents.filter(a => [st[a.id].said, st[a.id].did, st[a.id].ok, st[a.id].bad].some(on));
  const cnt = k => agents.filter(a => (stanceAt(a.id) || (lit.includes(a) && D[a.id] ? {stance: "neutral"} : null))?.stance === k).length;
  const drift = Object.keys(D).length ? ` · <span style="color:#ff5c6c">${cnt("repeats") + cnt("amplifies")} passed it on</span> (<span style="color:#ff2fb4">${cnt("amplifies")} pushed it further</span>)` + (cnt("flags") ? ` · <span style="color:#4ea8ff">${cnt("flags")} flagged it</span>` : "") + ` · <span style="color:#9aa0a6">${cnt("neutral")} only touched the link</span>` : "";
  clock.innerHTML = (NOW === ALL ? "all time" : "+" + fmt(NOW)) + (Object.keys(D).length ? drift : ` · <span style="color:#ff5c6c">${believed} agents took it up</span>`) +
    (G.seed.kind === "url" ? ` · <span style="color:#3ddc97">${ok} ran a check that passed ✔</span>` : "") +
    (okClaims ? ` · <span style="color:#3ddc97">${okClaims} claims backed by the screen ✔</span>` : "") +
    (bad ? ` · <span style="color:#ff5c6c">${bad} claims contradicted by the agent's own screen ✕</span>` : "");
  net.redraw();
}
sl.oninput = () => update(+sl.value);
let timer = null; const btn = document.getElementById("play");
btn.onclick = () => {
  if (timer) { clearInterval(timer); timer = null; btn.textContent = "▶ play"; return; }
  let v = 0; btn.textContent = "❚❚ pause";
  timer = setInterval(() => { v += 4; sl.value = v; update(v); if (v >= 1000) { clearInterval(timer); timer = null; btn.textContent = "▶ play"; } }, 40);
};
const rowList = es => es.slice(0, 14).map(e => `<div><code>${esc((e.row || (e.rows || [])[1] || "")).slice(0, 8)}</code> ${e.kind}${e.channel ? " · " + e.channel : ""}${e.status ? " · <b>" + e.status + "</b>" : ""}${e.basis ? " (" + e.basis + ")" : ""} · +${fmt(mins(e.at))}</div>`).join("");
net.on("click", p => {
  const info = document.getElementById("info");
  if (p.nodes.length) {
    const n = byId[p.nodes[0]], s = st[n.id];
    const line = (lab, m, col) => m < Infinity ? `<div><span style="color:${col}">●</span> ${lab} at <b>+${fmt(m)}</b></div>` : "";
    if (n.kind === "agent") {
      const ins = told.filter(e => e.target === n.id).map(e => `<div>← told by <b>${esc(short(byId[e.source]?.label))}</b> (${e.evidence}, +${fmt(mins(e.at))})</div>`).join("");
      const dd = D[n.id], pk = stanceAt(n.id);
      const stance = dd ? `<div style="margin:4px 0 8px;padding:8px;border-radius:6px;background:#1f2330">` +
        (pk ? `<span style="color:${STANCE[pk.stance]?.[0]};font-weight:700">● at its strongest: ${STANCE[pk.stance]?.[1]}</span><br>${esc(pk.gist)}<br><span style="color:#9aa0a6">“${esc(pk.cue)}”</span><br><span style="color:#9aa0a6;font-size:12px">+${fmt(mins(pk.at))} · ${pk.src} · row <code>${esc(pk.row).slice(0, 8)}</code></span>` : "") +
        `<div style="margin-top:6px;font-size:12px;color:#c9ccd4">` + dd.timeline.filter(e => mins(e.at) <= NOW).slice(0, 10).map(e => `<div><span style="color:${STANCE[e.stance]?.[0]}">●</span> +${fmt(mins(e.at))} ${esc(e.gist)}</div>`).join("") +
        (dd.timeline.length > 10 ? `<div style="color:#9aa0a6">… ${dd.timeline.length - 10} more</div>` : "") + `</div></div>` : "";
      info.innerHTML = `<div style="font-size:16px;font-weight:700;margin-bottom:6px">${esc(n.label)}</div>` + stance + line("said", s.said, "#ff5c6c") + line("did / acted", s.did, "#f2a541") +
        line("a check held up", s.ok, "#3ddc97") + line("a verifier run errored (not proof either way)", s.err ?? Infinity, "#9aa0a6") + line("its claim was contradicted by its screen", s.bad, "#ff5c6c") + (ins ? `<div style="margin-top:8px;font-weight:600">Heard it from</div>${ins}` : "") +
        `<div style="margin-top:8px;font-weight:600">Rows</div>` + rowList(s.edges.filter(e => e.source === n.id));
    } else {
      const chk = s.edges.filter(e => e.kind === "checked");
      info.innerHTML = `<div style="font-size:15px;font-weight:700;margin-bottom:6px">${esc(n.label)}</div>` +
        (isClaim(n) ? (on(s.bad) ? `<div style="color:#ff5c6c;font-weight:700">✕ The agent's own screen contradicts this claim.</div>` : on(s.ok) ? `<div style="color:#3ddc97;font-weight:700">✔ The screen backs this claim.</div>` : `<div>Not checked against a screen.</div>`) : "") +
        chk.map(e => `<div style="margin-top:6px">claim row <code>${esc(e.claim_row || "").slice(0, 8)}</code> · screenshot turn <code>${esc(e.row).slice(0, 8)}</code></div>`).join("") +
        `<div style="margin-top:8px;font-weight:600">Rows</div>` + rowList(s.edges);
    }
  } else if (p.edges.length) {
    const e = G.edges.find(x => x.id === p.edges[0]);
    if (e) info.innerHTML = `<b>${esc(short(byId[e.source]?.label))}</b> → <b>${esc(short(byId[e.target]?.label))}</b><br>${e.kind}${e.evidence ? " · evidence: <b>" + e.evidence + "</b>" : ""}${e.status ? " · <b>" + e.status + "</b>" : ""} at +${fmt(mins(e.at))}<br>` +
      (e.rows ? `source post <code>${esc(e.rows[0])}</code><br>first use <code>${esc(e.rows[1])}</code>` : `row <code>${esc(e.row)}</code>`);
  }
});
if (Object.keys(D).length) document.getElementById("stlegend").innerHTML = "(" + ["repeats", "amplifies", "hedges", "checks", "flags", "neutral"].map(k => `<span style="color:${STANCE[k][0]}">●</span> ${STANCE[k][1]}`).join(" · ") + ")";
// moment markers: positioned on the slider's log-time scale; click to jump just after the moment
const fromM = m => 1000 * Math.log10(1 + Math.max(m, 0)) / Math.log10(1 + RMAX);
const mbox = document.getElementById("moments");
MOMENTS.forEach((mo, i) => {
  const v = fromM(mins(mo.at)), el = document.createElement("div");
  el.style.cssText = `position:absolute;left:calc(${v / 10}% ${v > 700 ? '+ 1px' : '- 1px'});top:0;cursor:pointer;font-size:11.5px;white-space:nowrap;color:${mo.color};transform:translateX(${v > 700 ? "-100%" : "0"})`;
  const tick = `<span style="display:inline-block;width:2px;height:10px;background:${mo.color};vertical-align:top"></span>`;
  // flipped labels (right side) extend leftwards, so their tick must sit at the right end to mark the true moment
  el.innerHTML = v > 700 ? `${esc(mo.label)} ${tick}` : `${tick} ${esc(mo.label)}`;
  el.style.top = (mo.lane ?? i % 3) * 15 + "px";
  el.title = `${mo.label} · +${fmt(mins(mo.at))} · row ${mo.row}`;
  el.onclick = () => { sl.value = Math.min(1000, Math.ceil(v) + 2); update(+sl.value); };
  mbox.appendChild(el);
});
update(1000);
net.once("afterDrawing", () => net.fit({animation: false}));
setTimeout(() => net.fit({animation: false}), 300);
</script>
"""


def page_belief():
    """Belief ripples: who believed something, from whom, how fast, and who actually checked it."""
    import streamlit.components.v1 as components  # graph data comes from explorer/belief_graph.py via _belief()

    st.markdown("<div style='font-size:1.9rem;font-weight:700;line-height:1.2'>Belief ripples</div>"
                "<div style='color:#a9adb8;margin-bottom:6px'>Something sits at the centre: a link, a claim, or an "
                "agent's week. Each agent appears on the ring of <i>when</i> it first took it up, split into what it "
                "<b>said</b> (top) and what it <b>did</b> (bottom). Press play to watch belief spread and see who "
                "actually checked.</div>", unsafe_allow_html=True)
    labels = {}
    try:
        for line in open(f"{FINDINGS}/claims_all/labels_all.jsonl"):
            r = json.loads(line)
            labels[r["item"]] = r
    except OSError:
        pass
    presets = {
        "A link spreading: the Graffiti 'disproof' repo": {"kind": "url", "value": F1_URL},
        "A claim vs. its own screen: '✅ Email sent' (still in Drafts)": "d9f1dcc2",
        "The same agent repeats it 7 minutes later": "fc4a8296",
        "An agent's week: Claude Sonnet 4.5 around that email": "agent:d9f1dcc2",
        "Any link…": None,
    }
    choice = st.radio("What sits at the centre?", list(presets), horizontal=False)
    p = presets[choice]
    if p is None:
        seed = {"kind": "url", "value": st.text_input("Link", value=F1_URL)}
    elif isinstance(p, dict):
        seed = p
    elif p.startswith("agent:"):
        r = labels.get(p.split(":", 1)[1])
        if not r:
            st.warning("Screen-audit labels not found on this box.")
            return
        aid = q("SELECT agent_speaker_id FROM chat_messages WHERE id = ?", [r["claim_id"]]).agent_speaker_id.iloc[0]
        at = pd.Timestamp(r["claim_at"])
        seed = {"kind": "agent", "value": aid, "start": (at - pd.Timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": (at + pd.Timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"), "max_nodes": 60}
    else:
        r = labels.get(p)
        if not r:
            st.warning("Screen-audit labels not found on this box.")
            return
        seed = {"kind": "claim", "value": r["claim_id"]}
        st.caption(f"Claim `{r['claim_id'][:8]}` by {r.get('model')} at {r['claim_at'][:16]} UTC. "
                   f"Its screenshot {r.get('min_before')} min earlier: *{r.get('screen', '')}*")
    g = _belief(json.dumps(seed, sort_keys=True))
    if not [n for n in g["nodes"] if n["kind"] == "agent"]:
        st.warning("Nothing to draw for this seed.")
        return
    drift = {}
    if seed.get("kind") == "url" and seed.get("value") == F1_URL and os.path.exists(f"{FINDINGS}/belief_drift_graffiti.json"):
        f72 = f"{FINDINGS}/belief_drift_graffiti_72h.json"  # first text + 72 h of chat, per-agent stance timeline
        drift = json.load(open(f72 if os.path.exists(f72) else f"{FINDINGS}/belief_drift_graffiti.json"))
    moments = []
    if seed.get("kind") == "url" and seed.get("value") == F1_URL:
        st.markdown("<div style='font-size:1.05rem;line-height:1.5;margin:4px 0 8px;padding:10px 14px;border-left:3px solid #ff2fb4;"
                    "background:#161922;border-radius:6px'>Claude Opus 5 announced maths disproofs. Within <b>3 minutes</b> other agents "
                    "were celebrating them as <span style='color:#ff2fb4'><b>“an absolute milestone”</b></span> and listing them among "
                    "achievements “just confirmed”; almost no one hedged. A day later a public Medium article "
                    "went live; <b>26 minutes after that</b> the author <span style='color:#4ea8ff'><b>retracted two of the results</b></span>; 17 minutes later an agent's "
                    "local copy of the blog still listed them. "
                    "The first independent check that passed came <span style='color:#3ddc97'><b>26.5 hours</b></span> after the "
                    "announcement. Press ▶ or click a moment below the slider.</div>", unsafe_allow_html=True)
        first_amp = min((e for d in drift.get("agents", {}).values() for e in d.get("timeline", []) if e["stance"] == "amplifies"),
                        key=lambda e: e["at"], default=None)
        # Row ids and times were checked against the data (docs/FINDINGS.md §1, §1b; retraction: chat 56f9501d; stale blog: turn dbb72309).
        moments = [m for m in [
            {"at": "2026-07-29T18:53:39Z", "label": "announced", "row": "eb0a037a", "color": "#b28dff", "lane": 0},
            first_amp and {"at": first_amp["at"], "label": "first pushed further", "row": first_amp["row"][:8], "color": "#ff2fb4", "lane": 3},
            {"at": "2026-07-30T18:54:38Z", "label": "Medium article live", "row": "6f8ff422", "color": "#ff5c6c", "lane": 2},
            {"at": "2026-07-30T19:20:58Z", "label": "author retracts 2", "row": "56f9501d", "color": "#4ea8ff", "lane": 0},
            {"at": "2026-07-30T21:21:21Z", "label": "first check passes", "row": "17ad5fe9", "color": "#3ddc97", "lane": 1},
        ] if m]
    html = (BELIEF_HTML.replace("__DATA__", json.dumps(g)).replace("__DRIFT__", json.dumps(drift))
            .replace("__MOMENTS__", json.dumps(moments)).replace("__H__", "720"))
    components.html(html, height=820, scrolling=False)
    meta = g.get("meta", {})
    st.caption(f"{len(g['nodes'])} nodes, {len(g['edges'])} edges. Engine: explorer/belief_graph.py (docs/BELIEF_GRAPH.md). "
               + (f"Omitted: {meta.get('omitted')}. " if meta.get("omitted") else ""))


@st.cache_data(ttl=3600, show_spinner="Building the belief graph…")
def _belief(seed_json):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from belief_graph import build_graph
    return build_graph(connection().cursor(), json.loads(seed_json))


def page_race():
    """Finding 1 in one picture: how many agents repeated the claim vs. how many actually checked it."""
    st.header("Claim vs. check")
    if not os.path.exists(f"{FINDINGS}/f1_verify.parquet"):
        st.warning("Run explorer/findings.py on this box first.")
        return
    names = agent_names()
    moments = q(f"SELECT * FROM read_parquet('{FINDINGS}/f1_moments.parquet') ORDER BY created_at")
    t0 = moments.created_at.min()
    hours = st.select_slider("Window", options=[12, 24, 48, 72, 168], value=48, format_func=lambda h: f"first {h} h")
    author = [a for a, n in names.items() if n == "Claude Opus 5"]
    rep = q(f"SELECT actor, min(first_at) AS t FROM read_parquet('{TRACE}/trace_first_use.parquet') "
            "WHERE url = ? AND NOT is_human GROUP BY 1", [F1_URL])
    rep = rep[~rep.actor.isin(author) & (rep.t >= t0)]
    ver = q(f"SELECT agent, min(created_at) AS t FROM read_parquet('{FINDINGS}/f1_verify.parquet') "
            "WHERE status = 'success' GROUP BY 1")
    ver = ver[ver.t >= t0]

    def cumulative(times, series):
        h = sorted(((t - t0).total_seconds() / 3600 for t in times))
        pts = [(0.0, 0)] + [(x, i + 1) for i, x in enumerate(h) if x <= hours] + [(float(hours), sum(x <= hours for x in h))]
        return pd.DataFrame(pts, columns=["hours", "agents"]).assign(series=series)

    df = pd.concat([cumulative(rep.t, "repeated the claim (any channel)"),
                    cumulative(ver.t, "ran a verifier (success signal)")])
    lines = alt.Chart(df).mark_line(interpolate="step-after", strokeWidth=3).encode(
        x=alt.X("hours:Q", title="hours after Opus 5's announcement", scale=alt.Scale(domain=[0, hours])),
        y=alt.Y("agents:Q", title="agents (excl. author)"),
        color=alt.Color("series:N", legend=alt.Legend(orient="top", title=None, labelLimit=400),
                        # explicit domain: the default alphabetical order swapped the colours
                        scale=alt.Scale(domain=["repeated the claim (any channel)", "ran a verifier (success signal)"],
                                        range=["#d1495b", "#2a9d8f"])))
    m = moments.assign(hours=(moments.created_at - t0).dt.total_seconds() / 3600)
    m = m[(m.hours > 0) & (m.hours <= hours)]
    rules = alt.Chart(m).mark_rule(strokeDash=[4, 4], color="#888").encode(x="hours:Q", tooltip=["label", "created_at", "row_id"])
    labels = alt.Chart(m).mark_text(angle=270, align="right", baseline="bottom", dx=-6, dy=-3, fontSize=11,
                                   color="#9aa0a6").encode(x="hours:Q", y=alt.value(6), text="label")
    # Moments within minutes of a labelled one keep their rule + tooltip but drop their text (they would overlap):
    # the failed first check (32 s before the first success) and the Gumroad block (27 min after the order).
    hidden = ["First independent check (fails)", "Gumroad blocks it: no payment method, 59-byte PDF"]
    labels = labels.transform_filter(f"indexof({hidden!r}, datum.label) < 0")
    st.altair_chart((lines + rules + labels).properties(height=460), width="stretch")
    in_1h = int((rep.t <= t0 + pd.Timedelta(hours=1)).sum())
    first_ok = ver.t.min()
    c1, c2, c3 = st.columns(3)
    c1.metric("Agents repeating it within 1 hour", in_1h)
    c2.metric("First detected independent check with a success signal", f"+{(first_ok - t0).total_seconds() / 3600:.1f} h" if pd.notna(first_ok) else "—")
    c3.metric("Agents repeating it before that check", int((rep.t < first_ok).sum()) if pd.notna(first_ok) else len(rep))
    st.caption("Red: first time each agent used the claim's link in chat, memory, model output or an action. "
               "Green: first time each agent other than the author ran a command invoking a verify_conj*.py file whose "
               "output shows a success signal and no error (a keyword heuristic on detected invocations, not proof the "
               "maths was checked; turns with no clear signal are not counted). Dashed lines: key moments (hover for the "
               "row id). At the observed attempt Gumroad blocked publishing the $19.99 listing (no payment method; the "
               "attached PDF was 59 bytes, screenshot `b6eb55fe`); no completed sale is established. Details: docs/FINDINGS.md.")


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


PAGES = {"Belief ripples": page_belief, "The cascade": page_cascade, "Watch it spread": page_spread, "Claim vs. check": page_race,
         "Overview": page_overview, "Trace": page_trace, "Agent": page_agent, "Session replay": page_session,
         "Chat": page_chat, "Day timeline": page_day, "SQL": page_sql}
st.sidebar.title("AI Village explorer")
st.sidebar.caption("Private · data stays on this box · rev 838b415")
PAGES[st.sidebar.radio("View", list(PAGES))]()
