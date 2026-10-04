"""The #30 event contract, with missing-time records kept outside strict events.

Unknown actors stay unknown. Source text is inert evidence, never executable code.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

URL_RE = re.compile(r'https?://[^\s<>"\'`\\]+')
REDACTION_RE = re.compile(r'\[(?:REDACTED|CREDENTIAL|SERVICE|INFRA|ENV|ENCODED|PII)', re.I)
CVE_RE = re.compile(r'\bCVE-\d{4}-\d{4,}\b', re.I)
UNKNOWN_AGENT = 'unknown'


def log(step, **details):
    print(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'step': step, **details}), flush=True)


def timestamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp lacks an explicit timezone')
    return parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def urls_in_text(text):
    found = set()
    for match in URL_RE.finditer(text):
        raw = match.group().rstrip('.,;)]}')
        if REDACTION_RE.search(raw):
            continue
        try:
            parts = urlsplit(raw)
            if not parts.hostname or not re.fullmatch(r'[A-Za-z0-9.-]+', parts.hostname):
                continue
            parts.port  # Reject symbolic/invalid ports rather than pretending they are resolved URLs.
            userinfo, separator, host = parts.netloc.rpartition('@')
            netloc = userinfo + separator + host.lower() if separator else parts.netloc.lower()
            # Retain query order, path case and fragments; no network lookup or slug matching.
            found.add(urlunsplit((parts.scheme.lower(), netloc, parts.path,
                                  parts.query, parts.fragment)))
        except ValueError:
            continue
    return sorted(found)


@dataclass
class Observation:
    event: dict
    quality: dict

    def validate(self, *, dated=False):
        required = {'id', 'agent', 't', 'kind', 'channel', 'text', 'urls', 'tokens', 'src'}
        if set(self.event) != required:
            raise ValueError('Event fields do not match #30 contract')
        for name in ('id', 'agent', 'channel', 'text', 'src'):
            if not isinstance(self.event[name], str):
                raise ValueError(f'{name} must be a string')
        if self.event['kind'] not in ('said', 'did'):
            raise ValueError('Unknown event kind')
        for name in ('urls', 'tokens'):
            if not isinstance(self.event[name], list) or not all(isinstance(s, str) for s in self.event[name]):
                raise ValueError(f'{name} must contain strings')
        t = self.event['t']
        if t is not None and timestamp(t) != t:
            raise ValueError('Timestamp must be normalized ISO8601Z')
        if dated and t is None:
            raise ValueError('Undated record cannot be a strict #30 event')


class Adapter:
    dataset = ''

    def __init__(self, clip_chars=2000):
        if clip_chars < 0:
            raise ValueError('clip_chars must be nonnegative')
        self.clip_chars = clip_chars

    def observation(self, row_id, text, t, channel, kind, urls, tokens, **quality):
        if not isinstance(row_id, str) or not row_id:
            raise ValueError('Source row ID must be a nonempty string')
        event = {'id': f'{self.dataset}:{row_id}', 'agent': UNKNOWN_AGENT, 't': t,
                 'kind': kind, 'channel': channel, 'text': text[:self.clip_chars],
                 'urls': urls, 'tokens': tokens, 'src': f'{self.dataset}:{row_id}'}
        observation = Observation(event, {'id': event['id'], 'identity_quality': 'absent',
                                         'text_chars_original': len(text),
                                         'text_clipped': len(text) > self.clip_chars, **quality})
        observation.validate()
        return observation


def run(adapter):
    parser = argparse.ArgumentParser(description=adapter.__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='Strict, dated #30 events')
    parser.add_argument('--metadata', required=True, type=Path)
    parser.add_argument('--undated-output', type=Path, help='Separate observations with t=null; not strict events')
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--clip-chars', type=int, default=2000)
    args = parser.parse_args()
    adapter.clip_chars = args.clip_chars
    if args.clip_chars < 0:
        parser.error('--clip-chars must be nonnegative')
    paths = [p.resolve() for p in [args.output, args.metadata, args.profile, args.undated_output] if p]
    if len(set(paths)) != len(paths) or args.input.resolve() in paths:
        parser.error('Input and output paths must be distinct')
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter({k: 0 for k in ('rows', 'strict_events', 'undated_rows', 'text_clipped',
                                    'rows_with_urls', 'rows_with_tokens')})
    kinds = Counter(); times = Counter(); ids = set(); categories = {}
    log('adapter_start', dataset=adapter.dataset, input_bytes=args.input.stat().st_size)
    with args.output.open('w') as events, args.metadata.open('w') as metadata:
        undated = args.undated_output.open('w') if args.undated_output else None
        try:
            for row in adapter.rows(args.input):
                obs = adapter.adapt(row)
                e = obs.event
                if e['id'] in ids:
                    raise ValueError('Duplicate source row ID')
                ids.add(e['id']); counts['rows'] += 1
                kinds[obs.quality['source_kind']] += 1
                times[obs.quality['time_quality']] += 1
                for name in ('disposition', 'confidence', 'broad_class'):
                    if name in obs.quality:
                        categories.setdefault(name, Counter())[obs.quality[name]] += 1
                counts['text_clipped'] += obs.quality['text_clipped']
                counts['rows_with_urls'] += bool(e['urls'])
                counts['rows_with_tokens'] += bool(e['tokens'])
                target = events if e['t'] is not None else undated
                if e['t'] is not None:
                    obs.validate(dated=True); counts['strict_events'] += 1
                else:
                    counts['undated_rows'] += 1
                if target:
                    target.write(json.dumps(e, ensure_ascii=False) + '\n')
                metadata.write(json.dumps(obs.quality, ensure_ascii=False) + '\n')
                if counts['rows'] % 50000 == 0:
                    log('adapter_progress', dataset=adapter.dataset, rows=counts['rows'])
        finally:
            if undated:
                undated.close()
    digest = hashlib.sha256()
    with args.input.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    profile = {'dataset': adapter.dataset, 'input_sha256': digest.hexdigest(),
               'counts': dict(counts), 'source_kinds': dict(kinds), 'time_quality': dict(times),
               'categories': {name: dict(values) for name, values in categories.items()},
               'identified_agents': 0, 'identity_quality': 'absent', 'clip_chars': args.clip_chars,
               'source_schema': sorted(adapter.fields), 'notes': adapter.notes}
    args.profile.write_text(json.dumps(profile, indent=2) + '\n')
    log('adapter_done', dataset=adapter.dataset, **counts)
