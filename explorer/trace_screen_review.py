"""Audit #41's saved metadata without promoting screen labels to ground truth.

Source rows/images and generated reports belong in private storage, never git.
This reads existing outputs only; it does not fetch tars or run an annotator.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

NEXT_LABELS = frozenset({'done', 'not_done', 'unrelated', 'unclear'})


def read_jsonl(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def unique_index(rows, field):
    indexed = {}
    for row in rows:
        key = row[field]
        if key in indexed:
            raise ValueError(f'duplicate {field}: {key}')
        indexed[key] = row
    return indexed


def validated_labels(rows, expected):
    expected = list(expected)
    if len(expected) != len(set(expected)):
        raise ValueError('duplicate expected claim8')
    indexed = unique_index(rows, 'claim8')
    if set(indexed) != set(expected):
        raise ValueError(f'label coverage: missing={sorted(set(expected)-set(indexed))}; '
                         f'unexpected={sorted(set(indexed)-set(expected))}')
    for key, row in indexed.items():
        if row.get('label') not in NEXT_LABELS:
            raise ValueError(f'invalid label for {key}: {row.get("label")}')
    return indexed


def at(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def audit(records, labels):
    indexed = unique_index(records, 'claim8')
    if any(row['claim_id'][:8] != key for key, row in indexed.items()):
        raise ValueError('claim8 does not match claim_id')
    unique_index(records, 'claim_id')
    expected = {key for key, row in indexed.items() if row.get('next_turn')}
    labels = validated_labels(labels, expected)
    candidates, done, issues = [], [], []
    reused = defaultdict(list)
    for key, row in indexed.items():
        if not isinstance(row['acted_after'], bool):
            raise ValueError(f'acted_after must be boolean: {key}')
        if key not in expected:
            continue
        paired, claim, next_at = map(at, (row['paired_at'], row['claim_at'], row['next_at']))
        if next_at <= paired:
            issues.append({'claim8': key, 'issue': 'next_not_after_paired'})
        if next_at <= claim:
            issues.append({'claim8': key, 'issue': 'next_not_after_claim'})
        if (next_at-paired).total_seconds() > 15*60:
            issues.append({'claim8': key, 'issue': 'outside_15_minute_window'})
        label = labels[key]['label']
        if not row['acted_after'] and label == 'not_done':
            candidates.append(key)
        if label == 'done':
            done.append(key)
        reused[row['next_turn']].append({'claim8': key, 'label': label})
    groups = [group for group in reused.values() if len(group) > 1]
    return {
        'flags': len(records), 'next_screens': len(expected),
        'labels': dict(sorted(Counter(r['label'] for r in labels.values()).items())),
        'literal_gate_candidates': sorted(candidates),
        'done_labels': sorted(done), 'timing_issues': issues,
        'reused_next_turns': groups,
        'discordant_reused_next_turns': [g for g in groups if len({r['label'] for r in g}) > 1],
        'interpretation': 'Candidates require target-specific action and freshness review; '
                          'neither two not_done screens nor a later done label confirms historical truth.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    report = audit(read_jsonl(args.records), read_jsonl(args.labels))
    # Refuse to overwrite another investigator's checkpoint.
    with args.out.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(f"flags={report['flags']} next={report['next_screens']} "
          f"literal_gate_candidates={len(report['literal_gate_candidates'])}")


if __name__ == '__main__':
    main()
