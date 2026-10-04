"""Measure artifact recurrence and first observed co-use; never infer exposure edges.

Unknown agents cannot qualify an artifact as cross-agent. Missing timestamps are never
filled from row order or publication dates. Output IDs/statistics only; no text excerpts.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from explorer.adapters.contract import UNKNOWN_AGENT, log


def time_value(t):
    if t is None:
        return None
    parsed = datetime.fromisoformat(t.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must be timezone-aware')
    return parsed


def order_key(ref):
    return (ref['t'] is None, time_value(ref['t']) if ref['t'] else
            datetime.max.replace(tzinfo=timezone.utc), ref.get('agent', ref['id']))


def artifact_subtype(key):
    if key[0] == 'url':
        return 'literal_url'
    if key[1].startswith('redacted-sha256:'):
        return 'released_text_hash'
    if key[1].startswith('cve:'):
        return 'cve_mention'
    return 'other_token'


@dataclass
class Artifact:
    n: int = 0
    first_refs: list = field(default_factory=list)
    first_by_agent: dict = field(default_factory=dict)
    agents_with_undated_uses: set = field(default_factory=set)
    unknown_actor_uses: int = 0
    dated_uses: int = 0

    def add(self, event):
        self.n += 1
        t = time_value(event['t'])
        self.dated_uses += t is not None
        ref = {'id': event['id'], 'src': event['src'], 't': event['t']}
        self.first_refs.append(ref)
        self.first_refs.sort(key=order_key)
        del self.first_refs[5:]
        agent = event['agent']
        if not agent or agent == UNKNOWN_AGENT:
            self.unknown_actor_uses += 1
            return
        if t is None:
            self.agents_with_undated_uses.add(agent)
        prior = self.first_by_agent.get(agent)
        if prior is None or (t is not None and (prior['t'] is None or t < time_value(prior['t']))):
            self.first_by_agent[agent] = {'agent': agent, **ref}

    def result(self, key):
        has_undated = bool(self.agents_with_undated_uses)
        has_identity = bool(self.first_by_agent)
        order = sorted(self.first_by_agent.values(), key=order_key)
        lags = []
        if has_identity and not has_undated:
            for before, after in zip(order, order[1:]):
                lag = (time_value(after['t']) - time_value(before['t'])).total_seconds()
                lags.append({'earlier_row': before['id'], 'later_row': after['id'],
                             'seconds': lag, 'ordering': 'tied' if lag == 0 else 'strictly_later',
                             'evidence': 'first_observed_co_use_only'})
        # Hash the artifact's spelling so the aggregate contains no dataset URL excerpts.
        return {'artifact_id': key[0] + ':sha256:' + hashlib.sha256(key[1].encode()).hexdigest(),
                'artifact_type': key[0], 'observed_rows': self.n,
                'artifact_subtype': artifact_subtype(key),
                'known_agents': len(self.first_by_agent), 'unknown_actor_uses': self.unknown_actor_uses,
                'dated_uses': self.dated_uses, 'example_refs': self.first_refs,
                'first_use_order': order if has_identity and not has_undated else None,
                'inter_agent_lags': lags if has_identity and not has_undated else None,
                'order_quality': ('unidentifiable_missing_actor_identity' if not has_identity else
                                  'unidentifiable_undated_uses' if has_undated else
                                  'first_observed_timestamp_not_exposure'),
                'causal_source': None}


class SpreadAnalysis:
    def __init__(self):
        self.artifacts = {}; self.counts = Counter(); self.agents = set(); self.ids = set()

    def add(self, event):
        if event['id'] in self.ids:
            raise ValueError('Duplicate event ID: do not analyze dated exports plus their duplicate inventory')
        self.ids.add(event['id']); self.counts['rows'] += 1
        time_value(event['t'])
        self.counts['dated_rows'] += event['t'] is not None
        self.counts['undated_rows'] += event['t'] is None
        known = bool(event['agent'] and event['agent'] != UNKNOWN_AGENT)
        self.counts['known_actor_rows'] += known
        self.counts['unknown_actor_rows'] += not known
        if known:
            self.agents.add(event['agent'])
        artifacts = {('url', u) for u in event['urls']} | {('token', s) for s in event['tokens']}
        for key in artifacts:
            self.artifacts.setdefault(key, Artifact()).add(event)

    def result(self):
        shared = [(key, value) for key, value in self.artifacts.items() if len(value.first_by_agent) >= 2]
        recurrence = [(key, value) for key, value in self.artifacts.items() if value.n >= 2]
        ranked = sorted(shared, key=lambda pair: (-len(pair[1].first_by_agent), -pair[1].n, pair[0]))
        repeated = sorted(recurrence, key=lambda pair: (-pair[1].n, pair[0]))
        identifiable = bool(self.agents)
        return {'counts': dict(self.counts), 'known_agents': len(self.agents),
                'distinct_artifacts': len(self.artifacts),
                'distinct_artifacts_by_type': dict(Counter(k[0] for k in self.artifacts)),
                'distinct_artifacts_by_subtype': dict(Counter(artifact_subtype(k) for k in self.artifacts)),
                'repeated_across_rows': len(recurrence),
                'repeated_across_rows_by_type': dict(Counter(k[0] for k, _ in recurrence)),
                'repeated_across_rows_by_subtype': dict(Counter(artifact_subtype(k) for k, _ in recurrence)),
                'artifacts_shared_by_at_least_two_known_agents': len(shared) if identifiable else None,
                'known_cross_agent_artifact_lower_bound': len(shared),
                'cross_agent_status': ('observed_co_use_lower_bound' if identifiable
                                       else 'not_identifiable_missing_actor_identity'),
                'top_5_co_use_sequences': [v.result(k) for k, v in ranked[:5]],
                'top_5_row_recurrences_not_cascades': [v.result(k) for k, v in repeated[:5]],
                'source_inference': 'unsupported: no exposure/communication observations supplied',
                'limitations': ['Unknown actors are excluded, not replaced with row IDs or categories.',
                               'Order is first observed in this selected release, not first real-world use.',
                               'Ties do not establish direction; missing times do not establish order.',
                               'Recurrence can reflect templates, redaction or independent use.',
                               'A URLQuery report-reference URL is not an agent target URL.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--channel', help='Optional exact channel filter; never an actor identity')
    args = parser.parse_args()
    if args.output.resolve() in [p.resolve() for p in args.records]:
        parser.error('Output must not overwrite input records')
    analysis = SpreadAnalysis(); log('spread_start', inputs=len(args.records))
    for path in args.records:
        with path.open() as source:
            for line in source:
                if line.strip():
                    event = json.loads(line)
                    if args.channel is None or event['channel'] == args.channel:
                        analysis.add(event)
    result = analysis.result()
    result['channel_filter'] = args.channel
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    log('spread_done', **result['counts'], cross_agent_status=result['cross_agent_status'],
        distinct_artifacts=result['distinct_artifacts'], repeated_across_rows=result['repeated_across_rows'])


if __name__ == '__main__':
    main()
