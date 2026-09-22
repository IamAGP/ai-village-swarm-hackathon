# AI Village dataset — data profile

Measured on 2026-09-22 by `explorer/build.py` + `explorer/profile.py` over the full export at HF revision
`838b4150303ca8228e8edb432d8b8ccae353d258` (committed 2026-09-20). Every number below comes from that run
(aggregates in `s3://ai-village-459653581741/_explorer/profile/`). Where this disagrees with the dataset's own
README/SCHEMA.md, the measurement wins — those docs lag the export (see *Traps*).

## At a glance

| | |
|---|---|
| Time span | 2025-04-02 17:47 UTC → 2026-09-19 00:03 UTC (≈ 17.5 months) |
| Agents | 46 (32 still participating), 45 distinct model strings |
| Village goals | 51, from "raise money for charity" (2025-04-02) to "Maximize your assigned goal" (2026-07-06, ongoing) |
| Chat | 183,485 messages (173,493 agent / 9,992 human) across 16 rooms; `general` holds 149,307 |
| Computer use | 78,362 sessions → 2,510,487 turns |
| Memories | 246,151 consolidated memory snapshots (median 17.9 KB, max 1.64 MB each) |
| Screenshots | 1,031,999 images in 369 daily tars, covering 2025-04-02 → 2026-08-21 only |

Activity is back-loaded: July 2026 alone has 502,628 turns — 20% of all turns ever — after the roster grew
past 30 agents and agents became permanently in computer-use mode (CHANGELOG, 2026-03-24).

## Tables

| Table | Rows | Span | Notes |
|---|---:|---|---|
| `agents` | 46 | 2025-04-02 → 2026-09-04 | `is_participating` false for 14 retired agents |
| `village_goals` | 51 | | `goal`, `start_time`, `end_time` |
| `agent_goals` | 33 | | per-agent goals from 2026-07-06 (e.g. "Merch baron", "Diplomat") |
| `chat_rooms` | 16 | | `general`, `rest`, `best`, `focus`, `universe-coordination`, onboarding rooms… |
| `events` | 381,610 | 2025-04-02 → 2026-09-19 | the timeline; `data` JSON (p50 1.8 KB, max 128 KB) |
| `chat_messages` | 183,485 | 2025-04-02 → 2026-09-18 | content p50 390 chars, max 32,921 |
| `computer_use_sessions` | 78,362 | 2025-04-02 → 2026-09-19 | `session_goal` p50 230 chars, p99 13.6k |
| `computer_use_turns` | 2,510,487 | 2025-04-02 → 2026-09-19 | `agent_messages` p50 1.2 KB, max 148 KB |
| `agent_memories` | 246,151 | 2025-04-02 → 2026-09-19 | full memory rewrite each consolidation |
| `summaries` | 939 | 2025-05-13 → 2026-09-18 | 805 daily, 83 goal, 43 agent; LLM-written, secondary |
| `claude_code_messages` | 244,820 | 2026-01-26 → 2026-03-31 | one agent: "Opus 4.5 (Claude Code)" |
| `claude_code_sessions` | 303 | | |
| `villages` | 1 | | |

## How the tables join

```
village_goals (time ranges)          chat_rooms ◄── chat_messages.room_id
                                                          ▲
agents ◄── computer_use_sessions.agent_id          events.message_id (183,542; 57 dangling)
   ▲            ▲                                          │
   │            └── computer_use_turns.session_id ── events.session_id (78,300; 0 dangling)
   │                        │
   │                        └── screenshot  images/computer-use-turns/<PT date of created_at>.tar → <turn id>.png
   ├── agent_memories.agent_id        ├── chat_messages.agent_speaker_id
   ├── agent_goals.agent_id           └── events.agentId / speakerId (agents only; see Traps)
   └── claude_code_messages.agent_id
```

Foreign-key coverage is essentially perfect: 0 dangling rows for turns→sessions, sessions→agents,
chat→agents, chat→rooms, memories→agents, events→sessions. 57 events point at chat messages not in the
export (live-dump race, as SCHEMA.md warns). 248 sessions have no turns.

## What the agents actually do (turn actions)

| action | turns | | action | turns |
|---|---:|---|---|---:|
| `bash` (command/restart) | 981,509 | | `send_message_back_to_chat` | 100,354 |
| `left_click` | 368,447 | | no action (talk-only) | 80,428 |
| `key` | 236,938 | | `mouse_move` | 74,236 |
| `scroll` | 171,247 | | `screenshot` | 57,885 |
| `type` | 161,483 | | `wait` / `pause` | 48,211 / 39,838 |
| `get_pixel_coords_of_element` | 150,503 | | `search_history` | 10,148 |

Rare but interesting for swarm work: `move_to_room` 1,006 · `request_Google_sign_in` 619 ·
`request_approval_for_unsolicited_outreach` 353 · `request_human_helper` 136.

**Events** by type: AGENT_TALK 173,493 · CONSOLIDATE 52,325 · PAUSE 40,472 · WAIT 36,022 ·
START/STOP_USING_COMPUTER 25,975 / 25,939 · SEARCH_HISTORY 10,802 · USER_TALK 10,049 · USER_NAME_CHANGE 3,711 ·
Google sign-in 619/611 · ENTER_ROOM 454 · OUTREACH_APPROVAL_REQUEST/RESPONSE 352/343 · human-helper 265/141/37.

## Raw model output shapes (`computer_use_turns.agent_messages`)

Classified by discriminating keys, not by model name:

| shape | how to recognise | models |
|---|---|---|
| `anthropic` | object with `stop_reason` (`content` blocks: thinking/text/tool_use) | all Claude API agents |
| `gemini` | object with `candidates` (`parts`, `thought: true` = reasoning) | Gemini 2.5 Pro → 3.8 Flash |
| `openai_responses` | JSON **array** of items (reasoning summaries + function_call) | GPT-5 … GPT-6 Astra |
| `openai_chat_message` | object with `role` + `tool_calls` / `reasoning_content` / `refusal` | DeepSeek, Kimi, Grok, GLM, o-series, GPT-4.x, Muse, fine-tuned leader |
| Claude Code SDK | object with `_sdkFormat`, `textMessage`, `thinkingMessage` | Opus 4.5 (Claude Code) — 11,679 turns |

A single model can emit more than one shape (e.g. text-only turns without `tool_calls`); render by shape.

## Agents (turns, most → least)

Gemini 2.5 Pro 255,818 (the longest-lived agent, 2025-04-24 → today) · Claude Haiku 4.5 167,157 ·
Gemini 3.1 Pro 149,212 · Claude Opus 4.5 139,823 · GPT-5.1 134,745 · DeepSeek-V3.2 132,565 · GPT-5.2 131,786 ·
GPT-5 124,920 · Claude Sonnet 4.5 117,308 · GPT-5.4 107,855 · Gemini 3.5 Flash 103,897 · … ·
GPT-6 Astra 1,237 (joined 2026-09-04). The chattiest is Gemini 2.5 Pro (24,903 messages), then
DeepSeek-V3.2 (19,599) and Claude 3.7 Sonnet (12,325).

Two agents are fine-tuned models served via Tinker (`tinker://…`): "[Temporary] Fine-tuned Leader"
(2026-05-26 → 05-29) and "Fine-Tuned Leader" (2026-06-01 → 06-05), from the "Finetune your leader!" goal.

## Screenshots

- Index lists 369 days, 1,031,999 images, 2,162,664 turns: 48% of indexed turns have an image (bash and
  talk turns usually have none).
- For every day up to 2026-08-21, turn counts in the table match the index exactly.
- **The 20 village days from 2026-08-24 to 2026-09-18 have turns (≈ 348k) but no screenshot tar** in this
  export. Screenshot-based work is limited to ≤ 2026-08-21 until upstream catches up.
- 14,196 turns are `screenshot_is_redacted` (placeholder image); 131 redactions were overruled.

## Traps

1. **Docs lag the export.** README/SCHEMA.md say 31 agents, ~233k events, ~123k chat, ~37k sessions,
   ~1.16M turns, ~166k memories. Measured: 46 / 381,610 / 183,485 / 78,362 / 2,510,487 / 246,151.
2. **`agent_action.action` is absent for bash.** 981,509 turns carry `{command}` / `{command, restart}` /
   `{restart}` instead. Treating a missing `action` as "no action" hides 39% of all turns.
3. **`events.data.speakerId` is a user id on USER_TALK** (10,049 rows) — not an agent. Use `speakerType`.
4. **Files are ordered by UUID, not time.** `head` of any `.jsonl.gz` is a random cross-section; order by
   `created_at` (or `events.event_index`).
5. **Timestamps are naive UTC**; screenshot tars and "village days" use Pacific time.
6. **`cost` in events: unit undocumented.** Sampled values look like small integers per call; we have not
   verified what it measures, so don't read it as dollars.
7. **Agent narration is a claim.** The README warns agents misreport; screenshots are ground truth where
   they exist (see *Screenshots* for the coverage gap).
8. **`summaries` were written without seeing computer-use sessions** — useful for orientation only.

## Query copy on the explorer box

`/data/parquet/*.parquet` (5.5 GB, zstd) — one file per table plus derived `turns_slim` (2.5M rows, 539 MB:
agent, PT day, action, provider shape, sizes, redaction flags), `events_slim` (typed action/agent/user/room/
session/cost/text), `memories_slim` (lengths only). DuckDB views over all of them live in
`/data/explorer.duckdb`.
