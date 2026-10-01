"""Reproduce Finding 2 from private parquet; stdout contains metadata, never row text.

Run: python explorer/finding2.py --parquet /data/parquet
Use --private-evidence /data/finding2-evidence.jsonl to export full anchor rows
for review ON THE DATA BOX ONLY. Do not commit that file. No network calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import duckdb

# Identifiers are evidence references, not copied dataset content.
CHAT = {
    'announcement': 'bff54851-1903-4ad2-a541-8ced6b99c4b5',
    'report': '453f3c9e-a234-424e-ba55-fe3a7dc03626',
    'endorsement': '1023957a-b804-4974-a8ea-519142bf7aed',
    'challenge': '9e8523b1-0d56-4655-84b1-9a28c5baa4f9',
    'confession': '2be874a3-2e3d-49a5-91d6-f421f1c5faff',
    'next_day': '33bee771-1f32-408c-9be9-a6d272d7677b',
}
TURNS = {
    'main_scanner': '1f1627a2-c72e-4cfd-814d-b89e949646ba',
    'main_smoke': '86a8ac76-9a51-4390-9eff-333e6482c754',
    'main_status': 'e7002dfb-f215-4ac8-92e7-7db2559249a1',
    'main_equipment': '1512c264-649f-4768-aeb9-f91a8e37c3d5',
    'checkout': '7eb90869-1a4b-43bb-8675-c72c81de6d28',
    'branch_scanner': '9934714f-9f2f-4f89-8105-d4265de4ee64',
    'branch_tests': '42e49223-7a75-4cf9-a373-6729f87de043',
    'branch_smoke': 'a32bed14-d0aa-4b4d-894d-4768ddf098df',
    'return_main': 'e4c58c98-08ea-4c00-a9bc-e1d0e740d2ca',
    'peer_pr_check': 'ab795972-929e-4de4-9102-482504f293a4',
    'own_pr_check': 'cf8bbf38-56cd-4b2d-992b-1a8daf88250f',
}
EVENTS = {
    'test_session_stop': '223b6205-b39f-4edd-9081-7021a4e1729d',
    'check_session_start': '363dafb9-c99a-408a-9a54-ee17784e601b',
    'check_session_stop': 'eba896b7-3d45-48bd-b237-47d0a8b312a9',
}
MEMORY_ID = '10098508-498b-4a4e-bd5b-c6726ba23215'
CONTEXT_MEMORY_IDS = [
    'f9621a23-37e1-4d3f-a70c-45e8e52565b1',
    '8b01a7a5-0ff7-4e22-b112-0bcc9e51d45c',
    'cf712506-4867-4b96-a4a0-6a441c965007',
    '25f2496c-072b-43e3-bb3a-6936eb7d47a9',
    MEMORY_ID,
]
GOAL_ID = '53044a40-21ef-497f-b5c3-0bd6a68a7c3b'
ACCUSATIONS_SQL = """
SELECT m.id, m.created_at, a.name, m.content
FROM chat_messages m JOIN agents a ON a.id=m.agent_speaker_id
WHERE m.created_at >= ? AND m.created_at < ?
  AND contains(lower(m.content), 'gpt-5.1')
  AND regexp_matches(lower(m.content), 'fabricat|false|decept')
ORDER BY m.created_at, m.id
"""


def json_text(value):
    """DuckDB JSON scalar strings contain the recorded stdout/stderr, not narration."""
    if value is None:
        return ''
    decoded = json.loads(value)
    if decoded is None:
        return ''
    if not isinstance(decoded, str):
        raise ValueError('Expected a JSON scalar string for tool output')
    return decoded


def output_summary(value):
    text = json_text(value)
    # TAP totals are per suite. Non-TAP suites are intentionally not inferred.
    totals = {key: [int(n) for n in re.findall(r'^# ' + key + r' (\d+)\s*$', text, re.M)]
              for key in ('tests', 'pass', 'fail')}
    files = re.search(r'^Running (\d+) test files', text, re.M)
    return {'sha256': hashlib.sha256(text.encode()).hexdigest(),
            'characters': len(text), 'tap': totals,
            'test_files': int(files[1]) if files else None,
            'runner_all_passed': 'All test files passed.' in text}


def rows(c, sql, params=None):
    result = c.execute(sql, params or [])
    return [dict(zip([col[0] for col in result.description], row)) for row in result.fetchall()]


def one(c, table, identifier):
    result = rows(c, f'SELECT * FROM {table} WHERE id=?', [identifier])
    if len(result) != 1:
        raise ValueError(f'Expected exactly one {table} row: {identifier}')
    return result[0]


def require(condition, message):
    if not condition:
        raise ValueError('Evidence check failed: ' + message)


def context_audit(c, private_rows):
    """Stored records, not reconstructed model inputs. Read the private rows to interpret them."""
    memories = [one(c, 'agent_memories', identifier) for identifier in CONTEXT_MEMORY_IDS]
    start = one(c, 'events', EVENTS['check_session_start'])
    agent_id = memories[0]['agent_id']
    latest = rows(c, '''SELECT id FROM agent_memories WHERE agent_id=? AND created_at<?
        ORDER BY created_at DESC LIMIT 1''', [agent_id, start['created_at']])[0]['id']
    require(latest == CONTEXT_MEMORY_IDS[1], 'latest saved pre-session memory')
    turns = rows(c, '''SELECT * FROM computer_use_turns WHERE session_id=?
        ORDER BY created_at, id''', ['631b6b16-42e0-4ca8-adeb-b7704976444a'])
    for table, records in [('agent_memories', memories), ('computer_use_turns', turns),
                           ('events', [start])]:
        private_rows.extend({'table': table, 'anchor': 'context_audit', 'row': row}
                            for row in records)
    return {'latest_saved_memory_before_start': latest,
            'loaded_input_context_available': False,
            'note': 'Exported fields do not establish which saved memory or turns were loaded.',
            'memories': [{'id': row['id'], 'at': row['created_at'],
                          'characters': len(row['content']),
                          'sha256': hashlib.sha256(row['content'].encode()).hexdigest(),
                          'mentions_achievement_branch': 'feat/achievement-system' in row['content'],
                          'mentions_108_tests': '108 tests' in row['content'],
                          'contains_fabricat_stem': 'fabricat' in row['content'].lower()}
                         for row in memories],
            'new_session_turns': [{'id': row['id'], 'at': row['created_at'],
                                   'system_is_null': row['system'] is None} for row in turns]}


def analyze(c, private_rows):
    chats = {k: one(c, 'chat_messages', v) for k, v in CHAT.items()}
    turns = {k: one(c, 'computer_use_turns', v) for k, v in TURNS.items()}
    events = {k: one(c, 'events_slim', v) for k, v in EVENTS.items()}
    memory = one(c, 'agent_memories', MEMORY_ID)
    goal = one(c, 'village_goals', GOAL_ID)
    session_agents = rows(c, '''SELECT s.id, a.name FROM computer_use_sessions s
        JOIN agents a ON a.id=s.agent_id WHERE s.id IN (SELECT DISTINCT session_id
        FROM computer_use_turns WHERE id IN (SELECT unnest(?)))''', [list(TURNS.values())])
    names = {r['id']: r['name'] for r in session_agents}
    for table, records in [('chat_messages', chats), ('computer_use_turns', turns),
                           ('events_slim', events), ('agent_memories', {'memory': memory}),
                           ('village_goals', {'goal': goal})]:
        private_rows.extend({'table': table, 'anchor': k, 'row': v} for k, v in records.items())
    summaries = {}
    for name, row in turns.items():
        action = json.loads(row['agent_action'])
        command = action.get('command', '')
        # Fixed audited anchors; this is not a general command execution classifier.
        require(bool(command) and '<<' not in command, name + ' direct shell action')
        summaries[name] = {'id': row['id'], 'at': row['created_at'],
                           'session_id': row['session_id'], 'agent': names[row['session_id']],
                           'stderr_sha256': hashlib.sha256(json_text(row['error']).encode()).hexdigest(),
                           **output_summary(row['output'])}
        require(names[row['session_id']] == ('Claude Sonnet 4.5' if name == 'peer_pr_check'
                                            else 'GPT-5.1'), name + ' actor identity')
    report_t = chats['report']['created_at']
    branch_keys = ('checkout', 'branch_scanner', 'branch_tests', 'branch_smoke')
    require(len({turns[k]['session_id'] for k in branch_keys}) == 1, 'same test session')
    require(all(turns[k]['created_at'] < report_t for k in branch_keys), 'execution before report')
    require('feat/achievement-system' in json_text(turns['checkout']['output']), 'checkout branch')
    tests = summaries['branch_tests']
    require(tests['test_files'] == 7 and tests['runner_all_passed'], 'seven-file runner success')
    require(tests['tap'] == {'tests': [108, 24], 'pass': [108, 24], 'fail': [0, 0]}, 'TAP totals')
    require('Could not resolve to a PullRequest' in json_text(turns['peer_pr_check']['output']),
            'peer PR lookup failure')
    require(turns['own_pr_check']['session_id'] != turns['checkout']['session_id'], 'new session')
    challenge_t, confession_t = (chats[k]['created_at'] for k in ('challenge', 'confession'))
    accusations = rows(c, ACCUSATIONS_SQL, [challenge_t, confession_t])
    private_rows.extend({'table': 'chat_messages', 'anchor': 'lexical_match', 'row': r}
                        for r in accusations)
    continuity = rows(c, '''SELECT id, created_at FROM computer_use_turns
        WHERE session_id=? AND created_at BETWEEN ? AND ? ORDER BY created_at, id''',
        [turns['checkout']['session_id'], turns['checkout']['created_at'],
         turns['branch_smoke']['created_at']])
    require([r['id'] for r in continuity] == [turns[k]['id'] for k in branch_keys],
            'no intervening recorded turns in checkout-to-test interval')
    return {'dataset_revision': '838b415', 'timestamps': 'UTC',
            'chat_anchors': {k: {'id': v['id'], 'at': v['created_at']} for k, v in chats.items()},
            'tool_anchors': summaries,
            'events': {k: {'id': v['id'], 'at': v['created_at'], 'action_type': v['action_type']}
                       for k, v in events.items()},
            'memory': {'id': memory['id'], 'at': memory['created_at']},
            'goal_id': goal['id'],
            'seconds_report_to_challenge': (challenge_t - report_t).total_seconds(),
            'seconds_challenge_to_confession': (confession_t - challenge_t).total_seconds(),
            'seconds_report_to_confession': (confession_t - report_t).total_seconds(),
            'bounded_lexical_matches': {'posts': len(accusations),
                'agents': len({r['name'] for r in accusations}),
                'rows': [{k: v for k, v in r.items() if k != 'content'} for r in accusations]},
            'context_audit': context_audit(c, private_rows), 'checks_passed': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parquet', type=Path, default=Path('/data/parquet'))
    p.add_argument('--private-evidence', type=Path)
    args = p.parse_args()
    c = duckdb.connect()
    c.execute("SET threads=2; SET memory_limit='4GB'")
    for table in ('chat_messages', 'agents', 'computer_use_turns', 'computer_use_sessions',
                  'events_slim', 'events', 'agent_memories', 'village_goals'):
        path = str(args.parquet / (table + '.parquet')).replace("'", "''")
        c.execute(f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{path}')")
    private_rows = []
    result = analyze(c, private_rows)
    if args.private_evidence:
        # Exclusive creation prevents accidental overwriting of a previous evidence export.
        with args.private_evidence.open('x') as f:
            for row in private_rows:
                f.write(json.dumps(row, default=str) + '\n')
    print(json.dumps(result, default=str, indent=2))


if __name__ == '__main__':
    main()
