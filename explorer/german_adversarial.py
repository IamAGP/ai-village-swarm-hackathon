"""Independent raw-revision audit of Finding 3; imports no adapter/tracer code.

Run: python -m explorer.german_adversarial --input data/ext/german/revisions.jsonl.gz
     --output data/ext/results34/audit.json
Output contains aggregates and row references only, never bodies, labels or IP values.
"""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys


LINK = re.compile(r'''https?://[^\s\]\)\|<>"'}]+''')
WRAPPER = re.compile(r'^https?://([^/]+)/.*?(https?(%3A|:)|www\.)', re.I)


def features(body):
    urls = {x.rstrip('.,;:!?') for x in LINK.findall(body or '')}
    techniques = {"technique:" + m.group(1).lower()
                  for u in urls if (m := WRAPPER.match(u))}
    return urls, techniques


def log(step, **counts):
    print(json.dumps(dict(t=datetime.now(timezone.utc).isoformat(), step=step, **counts)),
          file=sys.stderr, flush=True)


def rate(successes, total):
    if not total:
        return dict(seen=0, n=0, percent=None, descriptive_wilson95=None)
    p, z = successes / total, 1.959963984540054
    d = 1 + z*z/total
    c = (p + z*z/(2*total))/d
    h = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/d
    return dict(seen=successes, n=total, percent=100*p,
                descriptive_wilson95=[100*(c-h), 100*(c+h)])


@dataclass(frozen=True)
class Revision:
    id: str
    page: str
    seq: int
    actor: str
    ip: str
    at: datetime
    grade: str
    uncertainty: int
    added: frozenset
    before: tuple  # (artifact, origin row id)
    new_proxy_uses: tuple  # technique once per added wrapped URL


class RevisionAudit:
    def __init__(self, raw):
        self.rows = {}
        self.label_ips = defaultdict(set)
        self.label_ip_first = {}
        self.popularity = defaultdict(set)
        self.time_reversals = 0
        self.missing_predecessors = sum(r.get('diff_base_reason') ==
                                        'earlier_revisions_not_published' for r in raw)
        states, last_at = {}, {}
        for r in sorted(raw, key=lambda r: (r['page_id'], int(r['seq']))):
            page, rid = r['page_id'], r['rev_id']
            at = datetime.fromisoformat(r['time'].replace('Z', '+00:00'))
            if rid in self.rows:
                raise ValueError('Duplicate revision ID')
            if page in last_at and at < last_at[page]:
                self.time_reversals += 1
            last_at[page] = at
            actor = (r.get('label') or '').strip()
            urls, techniques = features(r.get('body'))
            before = states.get(page, {})
            new_urls = urls - before.keys()
            added_tech = features(' '.join(sorted(new_urls)))[1]
            added = frozenset(new_urls | added_tech)
            now = urls | techniques
            state = {a: src for a, src in before.items() if a in now}
            for a in added:
                state.setdefault(a, rid)
            states[page] = state
            proxy_uses = tuple('technique:' + m.group(1).lower()
                               for u in sorted(new_urls) if (m := WRAPPER.match(u)))
            row = Revision(rid, page, int(r['seq']), actor, r.get('ip16') or '',
                           at, r['time_grade'], r.get('uncertainty_seconds', 0),
                           added, tuple(sorted(before.items())), proxy_uses)
            self.rows[rid] = row
            if actor:
                self.label_ips[actor].add(row.ip)
                key = actor, row.ip
                self.label_ip_first[key] = min(at, self.label_ip_first.get(key, at))
                self.popularity[page].add(actor)
        self.ordered = sorted(self.rows.values(), key=lambda r: (r.at, r.id))
        self.first = {}
        self.first_reqlog = {}
        self.exposures = defaultdict(list)
        self.edits = defaultdict(list)
        self.users = defaultdict(set)
        for r in self.ordered:
            if not r.actor:
                continue
            self.edits[r.actor].append(r)
            for a in r.added:
                self.first.setdefault((a, r.actor), r)
                if r.grade == 'reqlog':
                    self.first_reqlog.setdefault((a, r.actor), r)
                self.users[a].add(r.actor)
            for a, src in r.before:
                if self.rows[src].actor != r.actor:
                    self.exposures[a, r.actor].append((r, self.rows[src]))
        self.eligible = {a for a, users in self.users.items() if len(users) >= 10}
        self.prior_uses = defaultdict(list)
        self.ip_prior_times = defaultdict(list)
        self.ip_asof_times = defaultdict(list)
        for (a, actor), r in self.first.items():
            self.prior_uses[a].append(r)
            for ip in self.label_ips[actor]:
                self.ip_prior_times[a, ip].append(r.at)
                self.ip_asof_times[a, ip].append(max(r.at, self.label_ip_first[actor, ip]))
        for times in self.ip_prior_times.values():
            times.sort()
        for times in self.ip_asof_times.values():
            times.sort()
        self.edit_times = {actor: [r.at for r in rows] for actor, rows in self.edits.items()}

    def candidate_exposures(self, artifact, row, *, blank=False, hours=None,
                            strict=False, reqlog=False, separated=False, different_ip=False):
        proofs = []
        for edit, source in self.exposures[artifact, row.actor]:
            if edit.at > row.at or (strict and edit.at >= row.at):
                continue
            if not source.actor and not blank:
                continue
            if different_ip and source.ip == row.ip:
                continue
            if hours is not None and (row.at-edit.at).total_seconds() > hours*3600:
                continue
            if reqlog and (edit.grade != 'reqlog' or source.grade != 'reqlog'):
                continue
            if separated and (edit.at >= row.at or
                              (edit.at-source.at).total_seconds() <=
                              edit.uncertainty+source.uncertainty or
                              (row.at-edit.at).total_seconds() <=
                              row.uncertainty+edit.uncertainty):
                continue
            proofs.append((edit, source))
        # Match published earliest exposure, source-label, source-row tie ordering.
        return sorted(proofs, key=lambda p: (p[0].at, p[1].actor, p[1].id))

    def samples(self, *, first=None, unit='first_artifact', **options):
        first = self.first if first is None else first
        observations = list((a, r) for (a, _), r in first.items() if a in self.eligible)
        if unit == 'new_wrapped_url':
            observations = [(a, r) for r in self.ordered if r.actor
                            for a in r.added if a in self.eligible and not a.startswith('technique:')]
            observations += [(a, r) for r in self.ordered if r.actor
                             for a in r.new_proxy_uses if a in self.eligible]
        elif unit == 'first_label_wrapped_url':
            observations = [(a, r) for (a, _), r in first.items()
                            if a in self.eligible and not a.startswith('technique:')]
            observations += [('technique:' + m.group(1).lower(), r)
                             for (a, _), r in first.items() if not a.startswith('technique:')
                             and (m := WRAPPER.match(a))
                             and 'technique:' + m.group(1).lower() in self.eligible]
        result = []
        for a, r in observations:
            proofs = self.candidate_exposures(a, r, **options)
            source = proofs[0][1] if proofs else None
            ips = self.label_ips[r.actor]
            overlap = any((times := self.ip_prior_times[a, ip]) and times[0] < r.at
                          for ip in ips)
            asof_overlap = any(self.label_ip_first[r.actor, ip] <= r.at and
                               (times := self.ip_asof_times[a, ip]) and times[0] < r.at
                               for ip in ips)
            prior_count = bisect_left(self.edit_times[r.actor], r.at)
            pages = len({e.page for e in self.edits[r.actor][:prior_count]})
            result.append(dict(kind='technique' if a.startswith('technique:') else 'url',
                               row=r.id, artifact=a, seen=bool(proofs),
                               same_pair=bool(source and source.ip == r.ip),
                               label_pair_overlap=bool(source and source.actor and
                                   ips & self.label_ips[source.actor]),
                               any_prior_overlap=overlap,
                               asof_prior_overlap=asof_overlap,
                               prior_edits=prior_count, prior_pages=pages,
                               editors=len(self.popularity[r.page]),
                               current_edit_only=bool(proofs) and all(e.at == r.at for e, _ in proofs),
                               source_after_exposure=bool(source and source.at > proofs[0][0].at)))
        return result

    @staticmethod
    def summarize(samples):
        return {k: rate(sum(x['seen'] for x in samples if x['kind'] == k),
                        sum(x['kind'] == k for x in samples)) for k in ['technique', 'url']}

    @staticmethod
    def match(samples, covariate):
        strata = defaultdict(lambda: defaultdict(list))
        for s in samples:
            strata[s[covariate]][s['kind']].append(s['seen'])
        weighted, support, cells = Counter(), Counter(), []
        for value, groups in sorted(strata.items()):
            if not groups['technique'] or not groups['url']:
                continue
            weight = min(len(groups['technique']), len(groups['url']))
            cell = dict(value=value, overlap_weight=weight)
            for kind in ['technique', 'url']:
                n, seen = len(groups[kind]), sum(groups[kind])
                weighted[kind] += weight*seen/n
                support[kind] += n
                cell[kind] = rate(seen, n)
            cells.append(cell)
        total = sum(c['overlap_weight'] for c in cells)
        return dict(method='exact strata, common weight min(n_technique,n_url), no causal claim',
                    covariate=covariate, matched_weight_per_group=total,
                    supported_observations=dict(support),
                    percent={k: 100*weighted[k]/total if total else None
                             for k in ['technique', 'url']}, strata=cells)

    def run(self):
        base = self.samples()
        scenarios = {'published_reproduction': base,
                     'exclude_same_revision_ip_pair': [s for s in base if not s['same_pair']],
                     'exclude_source_adopter_label_ip_overlap': [s for s in base if not s['label_pair_overlap']],
                     'exclude_any_prior_user_label_ip_overlap': [s for s in base if not s['any_prior_overlap']],
                     'exclude_any_prior_user_asof_ip_overlap': [s for s in base if not s['asof_prior_overlap']],
                     'drop_same_ip_candidates_keep_denominator': self.samples(different_ip=True),
                     'include_blank_source_labels': self.samples(blank=True),
                     'reqlog_original_first_use': self.samples(first={k:r for k,r in self.first.items()
                                                                    if r.grade == 'reqlog'}, reqlog=True),
                     'reqlog_redefined_first_use': self.samples(first=self.first_reqlog, reqlog=True),
                     'exposure_within_72h': self.samples(hours=72),
                     'strictly_earlier_edit': self.samples(strict=True),
                     'strictly_earlier_edit_within_72h': self.samples(strict=True, hours=72),
                     'time_uncertainty_separated': self.samples(separated=True),
                     'per_new_wrapped_url': self.samples(unit='new_wrapped_url'),
                     'per_first_label_wrapped_url': self.samples(unit='first_label_wrapped_url'),
                     'exclude_wrapped_urls_from_control': [s for s in base
                         if s['kind'] == 'technique' or not WRAPPER.match(s['artifact'])]}
        strict = scenarios['strictly_earlier_edit']
        scenarios['strict_earlier_exclude_any_prior_ip_overlap'] = [s for s in strict if not s['any_prior_overlap']]
        scenarios['strict_earlier_exclude_asof_prior_ip_overlap'] = [s for s in strict if not s['asof_prior_overlap']]
        seen = [s for s in base if s['seen']]
        bands = [(1,2),(3,5),(6,20),(21,100),(101,100000)]
        technique_counts = Counter(a for a, _ in self.first if a.startswith('technique:'))
        burst = sorted([r for (a, _), r in self.first.items()
                        if a == 'technique:webcrawlerapi.com' and
                        r.at.date().isoformat() == '2026-06-18'], key=lambda r:(r.at,r.id))
        diagnostics = {}
        for kind in ['technique', 'url']:
            group = [s for s in base if s['kind'] == kind]
            ip_pairs = [s for s in seen if s['kind'] == kind and s['same_pair']][:5]
            current = [s for s in seen if s['kind'] == kind and s['current_edit_only']][:5]
            strict_asof = [s for s in scenarios['strict_earlier_exclude_asof_prior_ip_overlap']
                           if s['kind'] == kind and s['seen']][:5]
            def refs(rows):
                out = []
                for s in rows:
                    edit, origin = self.candidate_exposures(s['artifact'],self.rows[s['row']])[0]
                    out.append(dict(adoption=s['row'], exposure_edit=edit.id, origin=origin.id))
                return out
            diagnostics[kind] = dict(same_ip_pairs=refs(ip_pairs),
                                     adoption_edit_only=refs(current),
                                     strict_asof_survivors=refs(strict_asof),
                                     mean_prior_edits=sum(s['prior_edits'] for s in group)/len(group))
        return dict(census=dict(revisions=len(self.rows), labels=len(self.label_ips),
                               blank_labels=sum(not r.actor for r in self.ordered),
                               time_grades=dict(Counter(r.grade for r in self.ordered)),
                               sequence_time_reversals=self.time_reversals,
                               unpublished_predecessors=self.missing_predecessors,
                               eligible_artifacts=len(self.eligible),
                               eligible_techniques=sum(a.startswith('technique:') for a in self.eligible),
                               ip_blocks=len({r.ip for r in self.ordered}),
                               multi_ip_labels=sum(len(ips)>1 for ips in self.label_ips.values()),
                               max_labels_per_ip=max(Counter(ip for ips in self.label_ips.values()
                                                             for ip in ips).values()),
                               top_five_technique_label_counts=sorted(technique_counts.values(),reverse=True)[:5],
                               technique_count=len(technique_counts)),
                    burst=dict(labels=len(burst), duration_seconds=(burst[-1].at-burst[0].at).total_seconds(),
                               first_at=burst[0].at.isoformat(), last_at=burst[-1].at.isoformat(),
                               first_row=burst[0].id,last_row=burst[-1].id) if burst else None,
                    scenarios={name:self.summarize(rows) for name,rows in scenarios.items()},
                    seen_diagnostics={kind: dict(n=sum(s['kind']==kind for s in seen),
                          same_revision_ip=sum(s['kind']==kind and s['same_pair'] for s in seen),
                          label_ip_overlap=sum(s['kind']==kind and s['label_pair_overlap'] for s in seen),
                          any_prior_ip_overlap=sum(s['kind']==kind and s['any_prior_overlap'] for s in seen),
                          asof_prior_ip_overlap=sum(s['kind']==kind and s['asof_prior_overlap'] for s in seen),
                          adoption_edit_only=sum(s['kind']==kind and s['current_edit_only'] for s in seen),
                          source_after_exposure=sum(s['kind']==kind and s['source_after_exposure'] for s in seen))
                                      for kind in ['technique','url']},
                    popularity={f'{lo}-{hi}':self.summarize([s for s in base if lo<=s['editors']<=hi])
                                for lo,hi in bands},
                    matching={name:{cov:self.match(scenarios[name],cov)
                                    for cov in ['prior_edits','prior_pages']}
                              for name in ['published_reproduction',
                                           'exclude_any_prior_user_label_ip_overlap',
                                           'exclude_any_prior_user_asof_ip_overlap',
                                           'strictly_earlier_edit',
                                           'strict_earlier_exclude_any_prior_ip_overlap',
                                           'strict_earlier_exclude_asof_prior_ip_overlap']},
                    diagnostics=diagnostics)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.input.resolve() == args.output.resolve():
        p.error('Output must differ from input')
    log('read')
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    with gzip.open(args.input, 'rt') as f:
        raw = [json.loads(line) for line in f]
    log('reconstruct', revisions=len(raw))
    audit = RevisionAudit(raw)
    result = audit.run()
    result['input_sha256'] = digest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    log('done', census=result['census'], scenarios=result['scenarios'])


if __name__ == '__main__':
    main()
