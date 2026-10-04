"""Validate frozen independent agent-case labels and summarize retraction reach.

Inputs and row locators stay on the authorized data machine. Agreement is not accuracy.
This module never derives semantic labels from a keyword match.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
from statistics import median

try:
    from .trace_retraction import log, write_json
except ImportError:
    from trace_retraction import log, write_json

RETRACTED_AT = '2026-07-30 19:20:58.248631'
BINARY_FLAGS = ('a', 'b', 'c', 'mentioned', 'a_public', 'c_public', 'c_artifact', 'c_private')


def wilson(successes, n):
    """Descriptive 95% Wilson interval, not a population guarantee for this selected frame."""
    if not n:
        return None
    z = 1.959963984540054
    p = successes/n
    d = 1+z*z/n
    centre = (p+z*z/(2*n))/d
    half = z*((p*(1-p)/n+z*z/(4*n*n))**.5)/d
    return [max(0, centre-half), min(1, centre+half)]


def agreement(left, right):
    if len(left) != len(right) or not left:
        raise ValueError('Agreement requires equal nonempty paired cases')
    n = len(left)
    lc, rc = Counter(left), Counter(right)
    agree = sum(a == b for a, b in zip(left, right))
    observed = agree/n
    expected = sum(lc[k]*rc[k] for k in lc.keys() | rc.keys())/(n*n)
    return dict(n=n, agree=agree, fraction=observed, wilson95=wilson(agree,n),
                kappa=(observed-expected)/(1-expected) if expected < 1 else None,
                expected=expected)


def paired_bootstrap(left, right, draws=10000, seed=36):
    rng = random.Random(seed)
    values = []
    for _ in range(draws):
        ix = [rng.randrange(len(left)) for _ in left]
        k = agreement([left[i] for i in ix], [right[i] for i in ix])['kappa']
        if k is not None:
            values.append(k)
    values.sort()
    if not values:
        return dict(interval=None, valid_draws=0, draws=draws, seed=seed)
    return dict(interval=[values[int(.025*(len(values)-1))], values[int(.975*(len(values)-1))]],
                valid_draws=len(values), draws=draws, seed=seed)


class LabelAudit:
    def __init__(self, packet):
        self.packet = Path(packet)
        self.key = json.loads((self.packet/'key.json').read_text())
        self.cases = {x['case_id']: x for x in map(json.loads,(self.packet/'blind.jsonl').read_text().splitlines())}
        self.rows = self.key['rows']
        self.packet_hash = hashlib.sha256((self.packet/'blind.jsonl').read_bytes()).hexdigest()
        self.cut = datetime.fromisoformat(RETRACTED_AT)

    def load_frozen(self, folder, expected_sha256=None):
        folder = Path(folder)
        path = folder/'labels.jsonl'
        if (folder/'freeze.json').exists():
            freeze = json.loads((folder/'freeze.json').read_text())
            if expected_sha256 and freeze['sha256'] != expected_sha256:
                raise ValueError('Declared freeze hash differs from requested hash')
        elif expected_sha256:
            # External annotators can freeze with sha256sum rather than our JSON format.
            # The explicit hash must come from their freeze announcement, never an auto-read.
            freeze = dict(sha256=expected_sha256, packet_sha256=self.packet_hash,
                          external_manifest=str(folder/'MANIFEST.sha256'),
                          packet_binding='Shared review packet by investigator protocol; external manifest hashes labels only')
        else:
            raise ValueError('Need freeze.json or the externally announced frozen SHA-256')
        if hashlib.sha256(path.read_bytes()).hexdigest() != freeze['sha256']:
            raise ValueError('Frozen labels hash mismatch')
        if freeze['packet_sha256'] != self.packet_hash:
            raise ValueError('Labels refer to a different packet')
        labels = [json.loads(line) for line in path.read_text().splitlines()]
        return self.validate(labels), freeze

    def validate(self, labels):
        ids = [x['case_id'] for x in labels]
        if len(ids) != len(set(ids)) or set(ids) != set(self.cases):
            raise ValueError('Labels must cover exactly the packet cases once')
        result = {}
        for x in labels:
            case = x['case_id']
            for flag in BINARY_FLAGS:
                if x.get(flag) is not None and type(x[flag]) is not bool:
                    raise ValueError(f'{case}: nonboolean {flag}')
                if flag not in x:
                    raise ValueError(f'{case}: missing {flag}')
            if not x.get('reason'):
                raise ValueError(f'{case}: missing rationale')
            if x['mentioned'] is False and any(x[f] is True for f in ('a','b','c')):
                raise ValueError(f'{case}: positive flag without mention')
            if x['a_public'] is True and x['a'] is not True:
                raise ValueError(f'{case}: public spread requires a')
            if x['c'] is not None and all(x[f] is not None for f in ('c_public','c_artifact','c_private')):
                if x['c'] != any(x[f] for f in ('c_public','c_artifact','c_private')):
                    raise ValueError(f'{case}: stale subtype union mismatch')
            actor = self.key['cases'][case]['actor']
            for phase in ('a','b','c'):
                evidence = x.get(phase+'_evidence', [])
                if x[phase] is True and not evidence:
                    raise ValueError(f'{case}: positive {phase} needs evidence')
                for rid in evidence:
                    if rid not in self.rows or self.rows[rid]['actor'] != actor:
                        raise ValueError(f'{case}: evidence from another case or unknown row')
                    at = datetime.fromisoformat(self.rows[rid]['at'])
                    if (phase == 'a' and at >= self.cut) or (phase != 'a' and at < self.cut):
                        raise ValueError(f'{case}: wrong evidence phase')
                if evidence:
                    times = sorted(self.rows[r]['at'] for r in evidence)
                    if x.get('first_'+phase) != times[0]:
                        raise ValueError(f'{case}: endpoint must match evidence time')
                    if phase == 'c' and x.get('last_c') != times[-1]:
                        raise ValueError(f'{case}: stale endpoint must match evidence time')
            result[case] = x
        return result

    def summary(self, labels):
        displayed = {case:{r for c in value['contexts'] for r in c['row_ids']}
                     for case,value in self.cases.items()}
        gaps = {case:{phase:[r for r in x[phase+'_evidence'] if r not in displayed[case]]
                      for phase in ('a','b','c')}
                for case,x in labels.items()
                if any(r not in displayed[case] for phase in ('a','b','c') for r in x[phase+'_evidence'])}
        peers = [x for k,x in labels.items() if not self.cases[k]['source_author']]
        uptake = [x for x in peers if x['a'] is True]
        public = [x for x in peers if x['a_public'] is True]
        def reach(group):
            acknowledged = [x for x in group if x['b'] is True]
            lags = [(datetime.fromisoformat(x['first_b'])-self.cut).total_seconds() for x in acknowledged]
            return dict(n=len(group), acknowledged=len(acknowledged),
                        unresolved=sum(x['b'] is None for x in group),
                        observed_ack_seconds=sorted(lags), median_seconds=median(lags) if lags else None,
                        max_seconds=max(lags) if lags else None,
                        cases=[x['case_id'] for x in group])
        return dict(active_cases=len(labels), peer_cases=len(peers), source_author_excluded=True,witnesses_not_in_display=gaps,
                    mentioned_peers=sum(x['mentioned'] is True for x in peers),
                    never_mentioned_in_selected_frame=sum(x['mentioned'] is False for x in peers),
                    pre_uptake=reach(uptake), pre_public_or_prepared_outgoing=reach(public),
                    peer_flags={f:sum(x[f] is True for x in peers) for f in BINARY_FLAGS},
                    stale_after_uptake=sum(x['c'] is True for x in uptake),
                    stale_after_public=sum(x['c'] is True for x in public),
                    unresolved={f:sum(x[f] is None for x in peers) for f in BINARY_FLAGS})

    def compare(self, primary, secondary, draws=10000, cases=None):
        comparisons = {}
        for flag in (*BINARY_FLAGS, 'joint_abc'):
            a,b,disagreements = [],[],[]
            for case in sorted(self.cases if cases is None else cases):
                left = tuple(primary[case][f] for f in ('a','b','c')) if flag == 'joint_abc' else primary[case][flag]
                right = tuple(secondary[case][f] for f in ('a','b','c')) if flag == 'joint_abc' else secondary[case][flag]
                if left is None or right is None or (flag == 'joint_abc' and (None in left or None in right)):
                    continue
                a.append(left);b.append(right)
                if left != right:
                    disagreements.append(case)
            comparisons[flag] = dict(agreement(a,b), bootstrap=paired_bootstrap(a,b,draws), disagreements=disagreements) if a else dict(n=0,kappa=None)
        return comparisons


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet',required=True,type=Path)
    p.add_argument('--primary',required=True,type=Path)
    p.add_argument('--secondary',type=Path)
    p.add_argument('--secondary-sha256',help='Explicit hash from external reviewer freeze announcement')
    p.add_argument('--out',required=True,type=Path)
    args = p.parse_args()
    if args.out.exists():
        p.error('Preserve previous audit: output must be new')
    audit = LabelAudit(args.packet)
    primary,freeze = audit.load_frozen(args.primary)
    result = dict(packet_sha256=audit.packet_hash,primary_freeze=freeze,primary=audit.summary(primary),
                  limits='Selected keyword frame; imperfect masking; own-record timestamps, not receipt times; private uptake and artifact lag are distinct from public spread and mental belief.')
    if args.secondary:
        secondary,freeze2 = audit.load_frozen(args.secondary,args.secondary_sha256)
        cohort = [k for k,x in primary.items() if not audit.cases[k]['source_author'] and x['a'] is True]
        result.update(secondary_freeze=freeze2,secondary=audit.summary(secondary),
                      agreement=audit.compare(primary,secondary),
                      agreement_pre_uptake_peers=audit.compare(primary,secondary,cases=cohort))
    args.out.mkdir()
    write_json(args.out/'summary.json',result)
    log('label_audit_complete',paired=bool(args.secondary),cases=len(primary))


if __name__ == '__main__':
    main()
