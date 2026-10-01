"""Compare #17 outputs and draw blind changed/control samples; run beside private data.

Writes aggregate metrics plus PRIVATE blind/key JSONL files, never intended for git.
Sampling uses a SHA-256 ordering, independent of DuckDB version and scan order.
"""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', default='/data/trace_v6')
    parser.add_argument('--after', default='/data/trace_v7_codex17')
    parser.add_argument('--parquet', default='/data/parquet')
    parser.add_argument('--out', default='/data/eval_codex17')
    parser.add_argument('--seed', type=int, default=20261001)
    parser.add_argument('--n', type=int, default=25, help='Items per changed/control stratum')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='4GB'; SET threads=2")
    for name, directory in [('before', args.before), ('after', args.after)]:
        con.read_parquet(str(Path(directory) / 'trace_edges_scored.parquet')).create_view(name)
    for name in ['agents', 'chat_messages', 'computer_use_turns']:
        con.read_parquet(str(Path(args.parquet) / f'{name}.parquet')).create_view(name)
    con.execute('''CREATE VIEW changes AS
        SELECT a.*, b.evidence AS old_evidence, b.source_row AS old_source_row,
               b.target_row AS old_target_row
        FROM after a JOIN before b USING (url, target)''')
    def records(sql):
        cur = con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]
    metrics = {
        'seed': args.seed,
        'before': records('SELECT evidence, count(*) AS n FROM before GROUP BY evidence ORDER BY evidence'),
        'after': records('SELECT evidence, count(*) AS n FROM after GROUP BY evidence ORDER BY evidence'),
        'transitions': records('''SELECT old_evidence, evidence, count(*) AS n
            FROM changes GROUP BY ALL ORDER BY ALL'''),
        'coverage': records('''SELECT (SELECT count(*) FROM before) AS before_n,
            (SELECT count(*) FROM after) AS after_n, count(*) AS matched,
            count(*) FILTER (WHERE source_row IS DISTINCT FROM old_source_row) AS changed_sources,
            count(*) FILTER (WHERE target_row IS DISTINCT FROM old_target_row) AS changed_targets
            FROM changes'''),
        'flags': records('''SELECT count(*) FILTER (WHERE self_found) AS self_found,
            count(*) FILTER (WHERE named_old) AS named_old,
            count(*) FILTER (WHERE named_old AND evidence='explicit') AS explicit_old,
            count(*) FILTER (WHERE old_evidence='explicit' AND evidence<>'explicit') AS flipped
            FROM changes'''),
        'cues': records('''SELECT cue, count(*) AS n FROM
            (SELECT unnest(self_found_cues) AS cue FROM changes
             WHERE old_evidence='explicit' AND evidence<>'explicit')
            GROUP BY cue ORDER BY cue'''),
        'examples': records('''SELECT source_row, target_row, old_evidence, evidence, self_found_cues
            FROM changes WHERE old_evidence='explicit' AND evidence<>'explicit'
            ORDER BY target_row, url LIMIT 5'''),
    }
    pool = records("SELECT * FROM changes WHERE old_evidence='explicit'")
    def rank(row, salt):
        return hashlib.sha256(f'{args.seed}|{salt}|{row["url"]}|{row["target"]}'.encode()).hexdigest()
    selected = []
    for changed in (True, False):
        group = [r for r in pool if (r['evidence'] != 'explicit') == changed]
        for row in sorted(group, key=lambda r: rank(r, 'sample'))[:args.n]:
            selected.append((row, changed))
    selected.sort(key=lambda pair: rank(pair[0], 'shuffle'))
    names = dict(con.execute('SELECT id::VARCHAR, name FROM agents').fetchall())
    with (out / 'self_discovery.blind.jsonl').open('w') as blind, (out / 'self_discovery.key.jsonl').open('w') as key:
        for item, (row, changed) in enumerate(selected):
            source = con.execute('SELECT content FROM chat_messages WHERE id=?', [row['source_row']]).fetchone()
            if row['target_channel'] == 'chat':
                target = con.execute('SELECT content FROM chat_messages WHERE id=?', [row['target_row']]).fetchone()
            else:
                target = con.execute('''SELECT concat_ws(' ', agent_action::VARCHAR, agent_messages::VARCHAR)
                    FROM computer_use_turns WHERE id=?''', [row['target_row']]).fetchone()
            rec = dict(item=item, url=row['url'], candidate_source_agent=names.get(row['source']),
                       adopter_agent=names.get(row['target']), adopter_channel=row['target_channel'],
                       source_post_text=source[0] if source else None,
                       adopter_text=target[0] if target else None)
            blind.write(json.dumps(rec, ensure_ascii=False) + '\n')
            key.write(json.dumps(dict(item=item, changed=changed, **row), default=str) + '\n')
    metrics['sample'] = {'n': len(selected), 'changed': sum(changed for _, changed in selected),
                         'control': sum(not changed for _, changed in selected),
                         'context': 'full source post and full first-use turn; not truncated excerpts'}
    (out / 'metrics.json').write_text(json.dumps(metrics, indent=2, default=str) + '\n')
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == '__main__':
    main()
